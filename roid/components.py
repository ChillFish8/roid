from enum import IntEnum, auto
from typing import Optional
from pydantic import BaseModel

from roid.objects import PartialEmoji


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
