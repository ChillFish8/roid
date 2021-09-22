from typing import Optional, Dict, List, Union
from enum import IntEnum, auto

from pydantic import BaseModel

from roid.objects import User, Role, Channel, Member, PartialMessage
from roid.components import ComponentType


class CommandType(IntEnum):
    CHAT_INPUT = auto()
    USER = auto()
    MESSAGE = auto()


class CommandOptionType(IntEnum):
    SUB_COMMAND = auto()
    SUB_COMMAND_GROUP = auto()
    STRING = auto()
    INTEGER = auto()
    BOOLEAN = auto()
    USER = auto()
    CHANNEL = auto()
    ROLE = auto()
    MENTIONABLE = auto()
    NUMBER = auto()


class CommandChoice(BaseModel):
    name: str
    value: Union[str, int, float]


class CommandOption(BaseModel):
    type: CommandOptionType
    name: str
    description: str
    required: bool = False
    autocomplete: Optional[bool] = None
    choices: List[CommandChoice] = None
    options: List["CommandOption"] = None


CommandOption.update_forward_refs()


class InteractionType(IntEnum):
    PING = auto()
    APPLICATION_COMMAND = auto()
    MESSAGE_COMPONENT = auto()
    APPLICATION_COMMAND_AUTOCOMPLETE = auto()


class ResolvedData(BaseModel):
    users: Optional[Dict[int, User]]
    members: Optional[Dict[int, Member]]
    roles: Optional[Dict[int, Role]]
    channels: Optional[Dict[int, Channel]]
    messages: Optional[Dict[int, PartialMessage]]


class OptionData(BaseModel):
    name: str
    type: CommandOptionType
    value: Optional[
        Union[
            str,
            int,
            float,
            bool,
        ]
    ]
    options: Optional["OptionData"]
    focused: bool = False


OptionData.update_forward_refs()


class InteractionData(BaseModel):
    id: Optional[int]
    name: Optional[str]
    type: Optional[CommandType]
    resolved: Optional[ResolvedData]
    options: Optional[List[OptionData]]
    custom_id: Optional[str]
    component_type: Optional[ComponentType]
    values: Optional[List[str]]
    target_id: Optional[int]


class Interaction(BaseModel):
    id: int
    application_id: int
    type: InteractionType
    data: Optional[InteractionData]
    guild_id: Optional[int]
    channel_id: Optional[int]
    member: Optional[Member]
    user: Optional[User]
    token: str
    version: int
    message: Optional[PartialMessage]
