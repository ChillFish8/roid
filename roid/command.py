import asyncio
import functools

from enum import IntEnum, auto
from typing import List, Union, ForwardRef, Callable, Any, Coroutine, Optional

from pydantic import BaseModel, constr


class CommandType(IntEnum):
    CHAT_INPUT = auto()
    USER = auto()
    MESSAGE = auto()


class CommandOptionTypes(IntEnum):
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
    type: CommandOptionTypes
    name: str
    description: str
    required: bool = False
    choices: List[CommandChoice] = None
    options: List["CommandOption"] = None


CommandOption.update_forward_refs()


class CommandContext(BaseModel):
    type: CommandType
    name: constr(max_length=32, min_length=1)
    description: str
    application_id: str
    guild_id: Optional[str]
    options: Optional[List[CommandOption]]
    default_permission: bool


class Command:
    def __init__(
        self,
        callback,
        name: str,
        description: str,
        application_id: int,
        cmd_type: CommandType,
        guild_id: Optional[int],
        default_permissions: bool,
        options: Optional[List[CommandOption]],
    ):
        self.is_coroutine = asyncio.iscoroutinefunction(callback)
        self.callback = callback

        self.ctx = CommandContext(
            name=name,
            description=description,
            application_id=str(application_id),
            type=cmd_type,
            guild_id=str(guild_id),
            default_permission=default_permissions,
            options=options
        )

    def __call__(self, *args, **kwargs):
        if self.is_coroutine:
            return self.callback(*args, **kwargs)

        partial = functools.partial(self.callback, *args, **kwargs)
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, partial)

