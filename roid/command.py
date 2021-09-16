import asyncio
import functools
import inspect
from typing import List, Union, Optional, Any, Tuple, Dict

from pydantic import BaseModel, constr

from roid.exceptions import InvalidCommandOptionType
from roid.interactions import Interaction, CommandType, CommandOption, CommandOptionType
from roid.objects import User, Role, Channel, Member
from roid.extractors import extract_options


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
    return SetOption(default, name, description)


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


def get_options_from_spec(spec: inspect.FullArgSpec) -> List[Tuple[CommandOption, Any]]:
    options = []

    default_args = {}
    if spec.defaults is not None:
        delta = len(spec.args) - len(spec.defaults)
        default_args = dict(zip(spec.args[delta:], spec.defaults))

    for name, type_ in spec.annotations.items():
        option_type, description = OPTION_TYPE_PROCESSOR.get(type_)
        if option_type is None:
            raise InvalidCommandOptionType(
                f"type {type_!r} is not supported for command option types."
            )

        if name in default_args:
            default = default_args[name]
        else:
            default = Ellipsis

        required = default is Ellipsis
        if isinstance(default, SetOption):
            name = default.name or name
            description = default.description or description
            required = default.default is Ellipsis

        opt = CommandOption(
            name=name, description=description, type=option_type, required=required
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

        spec = inspect.getfullargspec(self.callback)
        annotations = spec.annotations

        self._pass_interaction: Optional[str] = None
        for param, type_ in annotations.items():
            if type_ is Interaction:
                self._pass_interaction = param
                break

        if options is None:
            options = []

        self._defaults: Dict[str, Any] = {}

        for option, default in get_options_from_spec(spec):
            options.append(option)
            self._defaults[option.name] = default

        self.ctx = CommandContext(
            name=name,
            description=description,
            application_id=str(application_id),
            type=cmd_type,
            guild_id=str(guild_id),
            default_permission=default_permissions,
            options=options,
        )

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
