from __future__ import annotations

import re
import asyncio
import functools
from enum import IntEnum, auto, Enum
from typing import (
    Optional,
    Union,
    List,
    Callable,
    Any,
    Coroutine,
    TYPE_CHECKING,
    Tuple,
    Type,
)
from pydantic import BaseModel, conint, AnyHttpUrl, constr, validate_arguments

from roid.exceptions import InvalidComponent, AbortInvoke
from roid.objects import PartialEmoji, ResponseFlags, ResponseType
from roid.state import COMMAND_STATE_TARGET
from roid.callers import OptionalAsyncCallable
from roid.state import PrefixedState

if TYPE_CHECKING:
    from roid.interactions import Interaction
    from roid.app import SlashCommands
    from roid.response import ResponsePayload, Response

    SyncOrAsyncCallable = Callable[
        [
            Any,
        ],
        Union[ResponsePayload, Coroutine[Any, Any, ResponsePayload]],
    ]

LimitedStr = constr(strip_whitespace=True, max_length=100, min_length=1)
EMOJI_REGEX = r"<(a)?:([a-zA-Z0-9]+):([0-9]{17,26})>"


class ComponentType(IntEnum):
    ACTION_ROW = auto()
    BUTTON = auto()
    SELECT_MENU = auto()


class SelectOption(BaseModel):
    label: LimitedStr
    value: LimitedStr
    description: Optional[LimitedStr] = None
    emoji: Optional[PartialEmoji]
    default: bool = False

    def __eq__(self, other: SelectOption):
        return self.label == other.label


class ButtonStyle(IntEnum):
    PRIMARY = auto()
    SECONDARY = auto()
    SUCCESS = auto()
    DANGER = auto()
    LINK = auto()


class ComponentContext(BaseModel):
    type: ComponentType
    custom_id: Optional[LimitedStr]
    disabled: bool
    style: Optional[ButtonStyle]
    label: Optional[str]
    emoji: Optional[PartialEmoji]
    url: Optional[AnyHttpUrl]
    options: List[SelectOption] = []
    placeholder: Optional[str]
    min_values: Optional[conint(ge=0, le=25)]
    max_values: Optional[conint(ge=0, le=25)]


class ActionRow(BaseModel):
    type: ComponentType = ComponentType.ACTION_ROW
    components: List[ComponentContext]


class SelectValue:
    @validate_arguments
    def __init__(
        self,
        value: LimitedStr,
        *,
        label: Optional[LimitedStr] = None,
        description: Optional[LimitedStr] = None,
        emoji: Optional[constr(strip_whitespace=True, regex=EMOJI_REGEX)] = None,
        default: bool = False,
    ):
        self.value = value
        self.label = label or value
        self.description = description
        self.default = default

        if emoji is not None:
            emoji = re.findall(EMOJI_REGEX, emoji)[0]
            animated, name, id_ = emoji
            emoji = PartialEmoji(id=id_, name=name, animated=bool(animated))

        self.emoji = emoji

    def __eq__(self, other):
        return self.value == other

    def __hash__(self):
        return hash(self.value)


class InvokeContext(dict):
    """A custom type wrapper to allow for detection in annotations."""

    def __init__(self, reference_id: str, state: PrefixedState, **kwargs):
        super().__init__(**kwargs)
        self.__state = state
        self.__reference_id = reference_id

    async def destroy(self):
        """
        Removes the context from the state.

        If this is ran, no populated context will be passed if the button is
        ran again.
        """
        await self.__state.remove(self.__reference_id)

    def purge_sync(self):
        """
        Removes the context from the state.

        If this is ran, no populated context will be passed if the button is
        ran again.
        """
        self.__state.remove_sync(self.__reference_id)


class Component(OptionalAsyncCallable):
    def __init__(
        self,
        app: SlashCommands,
        callback: SyncOrAsyncCallable,
        type_: ComponentType,
        custom_id: Optional[constr(strip_whitespace=True, regex="a-zA-Z0-9")] = None,
        style: Optional[ButtonStyle] = None,
        label: Optional[str] = None,
        emoji: Optional[PartialEmoji] = None,
        url: Optional[AnyHttpUrl] = None,
        options: Optional[List[SelectOption]] = None,
        disabled: bool = False,
        placeholder: Optional[str] = None,
        min_values: Optional[conint(ge=0, le=25)] = None,
        max_values: Optional[conint(ge=0, le=25)] = None,
        oneshot: bool = False,
        *,
        options_parameter: str = None,
    ):
        """
        A given discord component that invokes a callback that's
        either a regular function or a coroutine function.

        This is the wrapping type of both buttons and selects.

        If the callback takes a parameter with the type hinted as an `Interaction` then
        this will be automatically passed.

        Args:
            app:
                The app that's registering the components.
                This is required due to how the internal state manages
                the components context.

            callback:
                The function to be invoked when the component is triggered.

                If this is a link button is never called so it would be a good idea
                to use the helper function.


        """

        super().__init__(callback, None, validate=True)

        if options is None:
            options = []

        self.app = app
        self._ctx = ComponentContext(
            type=type_,
            custom_id=custom_id,
            style=style,
            label=label,
            emoji=emoji,
            url=url,
            options=options,
            disabled=disabled,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
        )

        self._target_options_parameter = options_parameter

        pass_context_to: Optional[str] = None
        for param, hint in self.annotations.items():
            if hint is InvokeContext and pass_context_to is not None:
                raise InvalidComponent(
                    f"component is already having context passed to {param!r}."
                )

            if hint is InvokeContext:
                pass_context_to = param

        self._oneshot = oneshot
        self._pass_context_to = pass_context_to

    @property
    def data(self) -> ComponentContext:
        return self._ctx

    def error(self, func: SyncOrAsyncCallable):
        self._register_error_handler(func)

    def __hash__(self):
        return hash(self._ctx.custom_id)

    async def __call__(self, interaction: Interaction) -> Any:
        try:
            resp, parent, ephemeral = await self._invoke(interaction)
        except Exception as e:
            if self._on_error is None:
                raise e from None
            resp, parent, ephemeral = await self._invoke_error_handler(interaction, e)

        if (not ephemeral) and resp.delete_parent and (parent is not None):
            await self.app._http.delete_interaction_message(parent.token)

        return resp

    async def _invoke(
        self, interaction: Interaction
    ) -> Tuple[Response, Interaction, bool]:
        kwargs, parent, ephemeral = await self._get_kwargs(interaction)

        if self._callback_is_coro:
            return await self._callback(**kwargs), parent, ephemeral

        partial = functools.partial(self._callback, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial), parent, ephemeral

    async def _get_kwargs(
        self,
        interaction: Interaction,
    ) -> Tuple[dict, Optional[Interaction], bool]:
        _, *reference_id = interaction.data.custom_id.split(":", maxsplit=1)

        if len(reference_id) == 0:
            reference_id = None
        else:
            reference_id = reference_id[0]

        state = self.app.state[COMMAND_STATE_TARGET]

        ctx = await state.get(reference_id)
        kwargs = {}
        if self._pass_context_to is not None and ctx is not None:
            kwargs[self._pass_context_to] = InvokeContext(reference_id, state, **ctx)

        if ctx is None and (self._pass_context_to not in self.defaults):
            raise AbortInvoke(
                content="This button has expired.",
                flags=ResponseFlags.EPHEMERAL,
                response_type=ResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
            )

        if self._oneshot:
            await state.remove(reference_id)

        if self._ctx.options is not None and interaction.data.values is not None:
            kwargs[self._target_options_parameter] = interaction.data.values

        if ctx is None:
            ephemeral = False
        else:
            ephemeral = ctx.get("ephemeral", False)

        return kwargs, ctx and ctx.get("parent"), ephemeral
