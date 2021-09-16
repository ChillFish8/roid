from typing import Optional, Dict
from enum import IntEnum, auto

from pydantic import BaseModel

from roid.command import CommandType
from roid.objects import User, Role, PartialChannel, PartialMember, PartialMessage

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
    resolved: Optional


class Interaction(BaseModel):
    id: int
    application_id: int
    type: InteractionType
    data: Optional[]

