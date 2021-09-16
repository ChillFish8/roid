import asyncio
import functools
import inspect

from enum import IntEnum, auto, Enum
from typing import List, Union, Optional, Any

from pydantic import BaseModel, constr

from roid.exceptions import InvalidCommandOptionType
from roid.interactions import Interaction
from roid.objects import User, Role, PartialChannel


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


class SetOption:
    def __init__(
        self,
        default: Union[str, int, float, None, bool, ...],
        name: Optional[str],
        description: Optional[str],
    ):
        self.default = default
        self.required = self.default is Ellipsis
        self.name = name
        self.description = description


def Option(
    default: Union[str, int, float, None, bool] = ...,
    *,
    name: str = None,
    description: str = None,
) -> Any:  # noqa
    return SetOption(default, name, description)


OPTION_TYPE_PROCESSOR = {
    int: (CommandOptionType.INTEGER, "Enter any whole number."),
    float: (CommandOptionType.NUMBER, "Enter any number."),
    str: (CommandOptionType.STRING, "Enter ome text."),
    bool: (CommandOptionType.BOOLEAN, "Enter either true or false."),
    Union[User, Role]: (CommandOptionType.MENTIONABLE, "Select a role or user."),
    User: (CommandOptionType.USER, "Select a user."),
    Role: (CommandOptionType.ROLE, "Select a role."),
    PartialChannel: (CommandOptionType.CHANNEL, "Select a channel"),
}


class Rename(Enum):
    """
    How to process the name of the option, this is only really useful when
    using the parameter based option inference.

    If you're manually defining an option in the parameters via the `Option` type hint
    this will be ignored.

    - `NONE` - Does not change the name of the option e.g. "foo_bar" -> "foo_bar"
    - `TITLE` - Splits the name on `_` and applies the `str.title()` method e.g. "foo_bar" -> "Foo Bar"
    - `CAPITALIZE` - Splits the name on `_` and applies the `str.capitalize()` e.g. "foo_bar" -> "Foo bar"
    - `UPPER` - Splits the name on `_` and applies the `str.upper()` e.g. "foo_bar" -> "FOO BAR"
    - `LOWER` - Splits the name on `_` and applies the `str.lower()` e.g. "foo_bar" -> "foo bar"
    """

    NONE = lambda x: x  # noqa
    TITLE = lambda x: x.replace("_", " ").title()  # noqa
    CAPITALIZE = lambda x: x.replace("_", " ").capitalize()  # noqa
    UPPER = lambda x: x.replace("_", " ").upper()  # noqa
    LOWER = lambda x: x.replace("_", " ").lower()  # noqa


def get_options_from_spec(
    rename_all: Rename,
    spec: inspect.FullArgSpec
) -> List[(CommandOption, Any)]:

    options = []

    default_args = {}
    if spec.defaults is not None:
        delta = len(spec.args) - len(spec.defaults)
        default_args = dict(zip(spec.args[delta:], spec.defaults))

    for parameter, type_ in spec.annotations:
        option_type, description = OPTION_TYPE_PROCESSOR.get(type_)
        if option_type is None:
            raise InvalidCommandOptionType(f"type {type_!r} is not supported for command option types.")

        if parameter in default_args:
            default = default_args[parameter]
        else:
            default = Ellipsis

        name = rename_all.value(parameter)
        required = default is not Ellipsis
        if isinstance(default, SetOption):
            name = default.name or name
            description = default.description or description
            required = default.default is not Ellipsis

        opt = CommandOption(
            name=name,
            description=description,
            type=option_type,
            required=required
        )

        options.append((opt, default))

    return options


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

        arg_spec = inspect.getfullargspec(self.callback)
        annotations = arg_spec.annotations

        self._pass_interaction: Optional[str] = None
        for param, type_ in annotations.items():
            if type_ is Interaction:
                self._pass_interaction = param
                break

        if options is None:
            options = []

        self.ctx = CommandContext(
            name=name,
            description=description,
            application_id=str(application_id),
            type=cmd_type,
            guild_id=str(guild_id),
            default_permission=default_permissions,
            options=options
        )

    def __call__(self, interaction: Interaction):
        kwargs = {}
        if self._pass_interaction is not None:
            kwargs[self._pass_interaction] = interaction

        if self.is_coroutine:
            return self.callback(**kwargs)

        partial = functools.partial(self.callback, **kwargs)
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, partial)

