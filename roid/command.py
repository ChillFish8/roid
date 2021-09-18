import asyncio
import functools
import inspect
import typing

from enum import Enum, IntEnum, auto
from typing import List, Union, Optional, Any, Tuple, Dict, Callable, Coroutine
from pydantic import BaseModel, constr, validate_arguments

from roid.exceptions import InvalidCommandOptionType
from roid.interactions import (
    Interaction,
    CommandType,
    CommandOption,
    CommandOptionType,
    CommandChoice,
)
from roid.objects import Role, Channel, Member, PartialMessage, User
from roid.extractors import extract_options
from roid.checks import CommandCheck
from roid.response import ResponsePayload


class CommandContext(BaseModel):
    id: Optional[str]
    type: CommandType
    name: constr(max_length=32, min_length=1)
    description: Optional[str]
    application_id: str
    guild_id: Optional[str]
    options: Optional[List[CommandOption]]
    choices: Optional[List[CommandChoice]]
    default_permission: bool

    def __eq__(self, other: "CommandContext"):
        return (
            self.name == other.name
            and self.description == other.description
            and self.application_id == other.application_id
            and self.guild_id == other.guild_id
            and self.options == other.options
            and self.choices == other.choices
            and self.default_permission == other.default_permission
        )


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


async def default_on_error(_: Interaction, exception: Exception) -> ResponsePayload:
    raise exception from None


class PassTarget(IntEnum):
    NONE = auto()
    MESSAGE = auto()
    USER = auto()
    MEMBER = auto()


class Command:
    def __init__(
        self,
        callback,
        name: str,
        application_id: int,
        description: Optional[str] = None,
        default_permissions: bool = False,
        guild_id: Optional[int] = None,
        cmd_type: CommandType = CommandType.CHAT_INPUT,
        register: bool = True,
    ):
        self.register = register
        self._is_coroutine = asyncio.iscoroutinefunction(callback)
        self._callback = callback

        spec = inspect.getfullargspec(self._callback)
        annotations = spec.annotations

        # Sets up how we should handle special case type hints.
        # The pass_target is only valid for MESSAGE and USER commands,
        # the value will be ignored for CHAT_INPUT commands.
        #
        # We dont want to be producing options for these special cases
        # so we also remove them from the annotations.
        self._pass_target: Tuple[PassTarget, str] = (PassTarget.NONE, "_")
        self._pass_interaction: Optional[str] = None
        for param, type_ in annotations.copy().items():
            if type_ is Interaction:
                del spec.annotations[param]
                self._pass_interaction = param
            elif type_ is PartialMessage:
                del spec.annotations[param]
                self._pass_target = (PassTarget.MESSAGE, param)
            elif type_ is User:
                del spec.annotations[param]
                self._pass_target = (PassTarget.USER, param)
            elif type_ is Member:
                del spec.annotations[param]
                self._pass_target = (PassTarget.MEMBER, param)
            elif type_ is Interaction and self._pass_target is not None:
                raise AttributeError(
                    f"interaction is already marked to be passed to {self._pass_target!r}"
                )

        options = []
        self._defaults: Dict[str, Any] = {}

        for option, default in get_details_from_spec(name, spec):
            if cmd_type in (CommandType.MESSAGE, CommandType.USER):
                raise ValueError(f"only CHAT_INPUT types can have options / input")

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

        self._callback = validate_arguments(self._callback)
        self._checks_pipeline: List[CommandCheck] = []
        self._on_error = default_on_error

    def _get_option_data(self, interaction: Interaction) -> dict:
        if interaction.data.options is None:
            return {}

        options = extract_options(interaction)

        for name, default in self._defaults.items():
            if name not in options:
                options[name] = default

        return options

    def __call__(self, interaction: Interaction):
        return self._run_checks_pipeline(interaction)

    def add_check(self, check: CommandCheck, *, at: int = -1):
        """
        Adds a check object to the command's check pipeline.

        Checks are ran in the order they are added and can directly
        modify the interaction data passed to the following checks.

        Args:
            check:
                The check object itself.

            at:
                The desired index to insert the check at.
                If the index is beyond the current length of the pipeline
                the check is appended to the end.
        """

        if 0 <= at < len(self._checks_pipeline):
            self._checks_pipeline.insert(at, check)
        else:
            self._checks_pipeline.append(check)

    def _get_invoke_kwargs(self, interaction: Interaction) -> dict:
        """
        Creates the kwarg dictionary for the command to be invoked based off
        of the interaction.

        If this is a non CHAT_INPUT command type the internal `pass_target`
        variable is used to determine if the targeted message / user should be
        passed directly.
        """

        cmd_type = self.ctx.type
        pass_target, pass_name = self._pass_target
        if cmd_type == CommandType.CHAT_INPUT:
            return self._get_option_data(interaction)
        elif cmd_type == CommandType.MESSAGE and pass_target == PassTarget.MESSAGE:
            return {
                pass_name: interaction.data.resolved.messages[
                    interaction.data.target_id
                ]
            }
        elif cmd_type == CommandType.USER and pass_target == PassTarget.USER:
            return {
                pass_name: interaction.data.resolved.users[interaction.data.target_id]
            }
        elif cmd_type == CommandType.USER and pass_target == PassTarget.MEMBER:
            target_id = interaction.data.target_id
            member = interaction.data.resolved.members[target_id]
            user = interaction.data.resolved.users[target_id]
            member.user = user
            return {pass_name: member}
        else:
            return {}

    async def _invoke(self, interaction: Interaction) -> ResponsePayload:
        kwargs = self._get_invoke_kwargs(interaction)

        if self._pass_interaction is not None:
            kwargs[self._pass_interaction] = interaction

        if self._is_coroutine:
            return await self._callback(**kwargs)

        partial = functools.partial(self._callback, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial)

    async def _run_checks_pipeline(self, interaction: Interaction) -> ResponsePayload:
        try:
            for check in self._checks_pipeline:
                interaction = await check(interaction)
        except Exception as e:
            return await self._on_error(interaction, e)
        else:
            return await self._invoke(interaction)

    def error(
        self,
        func: Callable[[Interaction, Exception], Coroutine[Any, Any, ResponsePayload]],
    ):
        """
        Maps the given error handling coroutine function to the commands general
        error handler.

        This will override the existing error callback.
        """
        self._on_error = func
