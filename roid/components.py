from __future__ import annotations

from enum import IntEnum, auto
from typing import Optional, Union, List, Callable, Any, Coroutine, TYPE_CHECKING
from pydantic import BaseModel, conint, AnyHttpUrl, constr

from roid.exceptions import InvalidComponent
from roid.objects import PartialEmoji
from roid.state import COMMAND_STATE_TARGET
from roid.callers import OptionalAsyncCallable
from roid.state import PrefixedState

if TYPE_CHECKING:
    from roid.app import SlashCommands
    from roid.interactions import Interaction
    from roid.response import ResponsePayload

    SyncOrAsyncCallable = Callable[
        [
            Any,
        ],
        Union[ResponsePayload, Coroutine[Any, Any, ResponsePayload]],
    ]

EMOJI_REGEX = r"<(a)?:([a-zA-Z0-9]+):([0-9]{17,26})>"


class ComponentType(IntEnum):
    ACTION_ROW = auto()
    BUTTON = auto()
    SELECT_MENU = auto()


class SelectOption(BaseModel):
    label: str
    value: str
    description: Optional[str] = None
    emoji: Optional[PartialEmoji]
    default: bool = False


class ButtonStyle(IntEnum):
    PRIMARY = auto()
    SECONDARY = auto()
    SUCCESS = auto()
    Danger = auto()
    Link = auto()


class ComponentContext(BaseModel):
    type: ComponentType
    custom_id: Optional[str]
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


class InvokeContext(dict):
    """A custom type wrapper to allow for detection in annotations."""

    def __init__(self, reference_id: str, state: PrefixedState, **kwargs):
        super().__init__(**kwargs)
        self.__state = state
        self.__reference_id = reference_id

    async def purge(self):
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
    ):
        super().__init__(callback, None)

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

    async def _get_kwargs(self, interaction: Interaction) -> dict:
        _, *reference_id = interaction.data.custom_id.split(":", maxsplit=1)

        if len(reference_id) == 0:
            reference_id = None
        else:
            reference_id = reference_id[0]

        kwargs = {}
        if self._pass_context_to is not None:
            state = self.app.state[COMMAND_STATE_TARGET]
            ctx = await state.get(reference_id)

            if ctx is None and (self._pass_context_to not in self.defaults):
                kwargs[self._pass_context_to] = {}
            elif ctx is not None:
                kwargs[self._pass_context_to] = InvokeContext(
                    reference_id, state, **ctx
                )

                if self._oneshot:
                    await state.remove(reference_id)
        return kwargs
