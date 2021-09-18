from __future__ import annotations

import json
import re

from enum import IntEnum, auto
from typing import Optional, Union, List, Callable, Any, Coroutine, TYPE_CHECKING
from pydantic import BaseModel, conint, validate_arguments, constr, AnyHttpUrl

from roid.objects import PartialEmoji

if TYPE_CHECKING:
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


class Component:
    def __init__(
        self,
        callback: SyncOrAsyncCallable,
        type_: ComponentType,
        custom_id: Optional[str] = None,
        style: Optional[ButtonStyle] = None,
        label: Optional[str] = None,
        emoji: Optional[PartialEmoji] = None,
        url: Optional[AnyHttpUrl] = None,
        options: Optional[List[SelectOption]] = None,
        disabled: bool = False,
        placeholder: Optional[str] = None,
        min_values: Optional[conint(ge=0, le=25)] = None,
        max_values: Optional[conint(ge=0, le=25)] = None,
    ):
        if options is None:
            options = []

        if custom_id is None and url is None:
            custom_id = callback.__qualname__

        self._callback = callback
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

    @property
    def data(self) -> ComponentContext:
        return self._ctx

    def __hash__(self):
        return hash(self._ctx.custom_id)

    async def __call__(self, interaction: Interaction):
        print(json.dumps(interaction.dict(), indent=4))


@validate_arguments
def button(
    label: str,
    style: ButtonStyle,
    *,
    custom_id: Optional[str] = None,
    disabled: bool = False,
    emoji: constr(strip_whitespace=True, regex=EMOJI_REGEX) = None,
    url: Optional[AnyHttpUrl] = None,
):
    """
    Attaches a button component to the given command.

    Args:
        style:
            The set button style. This can be any set style however url styles
            require the url kwarg and generally would be better off using
            the hyperlink helper decorator.

        custom_id:
            The custom button identifier. If you plan on having long running
            persistent buttons e.g. reaction roles. You will probably want to
            set this. Otherwise the function name + command name is used to
            generate a id.
            (Naturally changing the name of the function will invalidate old buttons.)

        disabled:
            If the button should start disabled or not.

        label:
            The button label / text shown on the button.

        emoji:
            The set emoji for the button. This should be a custom emoji
            not a unicode emoji (use the `label` field for that.)

        url:
            The hyperlink url, if this is set the function body is not invoked
            on click along with the `emoji` and `style` field being ignored.
    """

    if emoji is not None:
        emoji = re.findall(EMOJI_REGEX, emoji)[0]
        animated, name, id_ = emoji
        emoji = PartialEmoji(id=id_, name=name, animated=bool(animated))

    def wrapper(func):
        component = Component(
            callback=func,
            type_=ComponentType.BUTTON,
            style=style,
            custom_id=custom_id,
            disabled=disabled,
            label=label,
            emoji=emoji,
            url=url,
        )

        return component

    return wrapper


@validate_arguments
def select(
    *,
    custom_id: Optional[str] = None,
    disabled: bool = False,
    placeholder: str = "Select an option.",
    min_values: conint(ge=0, le=25) = 1,
    max_values: conint(ge=0, le=25) = 1,
):
    """
    A select menu component.

    This will occupy and entire action row so any components sharing the row
    will be rejected (done on a first come first served basis.)

    Args:
        custom_id:
            The custom button identifier. If you plan on having long running
            persistent buttons e.g. reaction roles. You will probably want to
            set this. Otherwise the function name + command name is used to
            generate a id.
            (Naturally changing the name of the function will invalidate old buttons.)

        disabled:
            If the button should start disabled or not.

        placeholder:
            The placeholder text the user sees while the menu is not focused.

        min_values:
            The minimum number of values the user must select.

        max_values:
            The maximum number of values the user can select.
    """

    def wrapper(func):
        component = Component(
            callback=func,
            type_=ComponentType.SELECT_MENU,
            custom_id=custom_id,
            disabled=disabled,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
        )

        return component

    return wrapper
