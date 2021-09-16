from typing import Optional, Dict, List, Union
from enum import IntEnum, auto

from pydantic import BaseModel

from roid.command import CommandType, CommandOption
from roid.objects import User, Role, PartialChannel, PartialMember, PartialMessage
from roid.components import ComponentType

class InteractionType(IntEnum):
    PING = auto()
    APPLICATION_COMMAND = auto()
    MESSAGE_COMPONENT = auto()


class ResolvedData(BaseModel):
    users: Optional[Dict[int, User]]
    members: Optional[Dict[int, PartialMember]]
    roles: Optional[Dict[int, Role]]
    channels: Optional[Dict[int, PartialChannel]]
    messages: Optional[Dict[int, PartialMessage]]


class InteractionData(BaseModel):
    id: int
    name: str
    type: CommandType
    resolved: Optional[ResolvedData]
    options: Optional[List[CommandOption]]
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
    member: Optional[PartialMember]
    user: Optional[User]
    token: str
    version: int
    message: Optional[PartialMessage]
