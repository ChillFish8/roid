from __future__ import annotations

import json

from enum import IntEnum, auto
from typing import Optional, Union, List, Callable, Any, Coroutine, TYPE_CHECKING
from pydantic import BaseModel, conint, AnyHttpUrl, constr

from roid.objects import PartialEmoji

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


class Component:
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
    ):
        if options is None:
            options = []

        self.app = app
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
