import asyncio
import functools
import inspect
from enum import Enum, IntEnum
from typing import List, Union, Optional, Any, Tuple, Dict

import typing
from pydantic import BaseModel, constr, validate_arguments

from roid.exceptions import InvalidCommandOptionType
from roid.interactions import (
    Interaction,
    CommandType,
    CommandOption,
    CommandOptionType,
    CommandChoice,
)
from roid.objects import Role, Channel, Member
from roid.extractors import extract_options


class CommandContext(BaseModel):
    type: CommandType
    name: constr(max_length=32, min_length=1)
    description: str
    application_id: str
    guild_id: Optional[str]
    options: Optional[List[CommandOption]]
    choices: Optional[List[CommandChoice]]
    default_permission: bool


class SetValue:
    def __init__(
        self,
        default: Union[str, int, float, None, bool],
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
    return SetValue(default, name, description)


VALID_CHOICE_TYPES = (
    CommandOptionType.STRING,
    CommandOptionType.NUMBER,
    CommandOptionType.INTEGER,
)

OPTION_TYPE_PROCESSOR = {
    int: (CommandOptionType.INTEGER, "Enter any whole number."),
    float: (CommandOptionType.NUMBER, "Enter any number."),
    str: (CommandOptionType.STRING, "Enter some text."),
    bool: (CommandOptionType.BOOLEAN, "Enter either true or false."),
    Union[Member, Role]: (
        CommandOptionType.MENTIONABLE,
        "Select a role or member.",
    ),
    Member: (CommandOptionType.USER, "Select a member."),
    Role: (CommandOptionType.ROLE, "Select a role."),
    Channel: (CommandOptionType.CHANNEL, "Select a channel"),
}


def get_details_from_spec(
    cmd_name: str,
    spec: inspect.FullArgSpec,
) -> List[Tuple[CommandOption, Any]]:
    options = []

    default_args = {}
    if spec.defaults is not None:
        delta = len(spec.args) - len(spec.defaults)
        default_args = dict(zip(spec.args[delta:], spec.defaults))

    for name, type_ in spec.annotations.items():
        choice_blocks = []

        original = typing.get_origin(type_)
        if original is typing.Literal:
            target_type = None
            for v in typing.get_args(type_):
                if target_type is None:
                    target_type = type(v)
                elif type(v) is not target_type:
                    raise TypeError(
                        f"(command: {cmd_name!r}, parameter: {name!r}) literal must be the same type."
                    )

                choice_blocks.append(CommandChoice(name=v, value=v))
            type_ = target_type
        elif issubclass(type_, (Enum, IntEnum)):
            target_type = None
            for e in type_:
                if target_type is None:
                    target_type = type(e.value)
                elif type(e.value) is not target_type:
                    raise TypeError(
                        f"(command: {cmd_name!r}, parameter: {name!r}) enum must contain all the same types."
                    )

                choice_blocks.append(CommandChoice(name=str(e.value), value=e.value))
            type_ = target_type

        result = OPTION_TYPE_PROCESSOR.get(type_)
        if result is None:
            raise InvalidCommandOptionType(
                f"(command: {cmd_name!r}) type {type_!r} is not supported for command option / choice types."
            )

        option_type, description = result
        if name in default_args:
            default = default_args[name]
        else:
            default = Ellipsis

        required = default is Ellipsis
        if isinstance(default, SetValue):
            name = default.name or name
            description = default.description or description
            required = default.default is Ellipsis
        elif len(choice_blocks) > 0:
            description = "Select an option from the list."

        kwargs = dict(
            name=name,
            description=description,
            type=option_type,
            required=required,
        )

        if (len(choice_blocks) > 0) and (option_type not in VALID_CHOICE_TYPES):
            raise InvalidCommandOptionType(
                f"{type_!r} cannot be inferred for a choices option"
            )

        if len(choice_blocks) > 0:
            kwargs["choices"] = choice_blocks

        opt = CommandOption(**kwargs)
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
    ):
        self.is_coroutine = asyncio.iscoroutinefunction(callback)
        self.callback = callback

        spec = inspect.getfullargspec(self.callback)
        annotations = spec.annotations

        self._pass_interaction: Optional[str] = None
        for param, type_ in annotations.items():
            if type_ is Interaction:
                self._pass_interaction = param
                break

        options = []
        self._defaults: Dict[str, Any] = {}

        for option, default in get_details_from_spec(name, spec):
            options.append(option)
            self._defaults[option.name] = default

            if option.choices is None:
                continue

        self.ctx = CommandContext(
            name=name,
            description=description,
            application_id=str(application_id),
            type=cmd_type,
            guild_id=str(guild_id),
            default_permission=default_permissions,
            options=options if len(options) != 0 else None,
        )

        self.callback = validate_arguments(self.callback)

    def get_option_data(self, interaction: Interaction) -> dict:
        if interaction.data.options is None:
            return {}

        options = extract_options(interaction)

        for name, default in self._defaults.items():
            if name not in options:
                options[name] = default

        return options

    def __call__(self, interaction: Interaction):
        kwargs = self.get_option_data(interaction)
        if self._pass_interaction is not None:
            kwargs[self._pass_interaction] = interaction

        if self.is_coroutine:
            return self.callback(**kwargs)

        partial = functools.partial(self.callback, **kwargs)
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, partial)
