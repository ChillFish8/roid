from __future__ import annotations

import uuid
import inspect
import typing

from enum import Enum, IntEnum, auto
from typing import (
    List,
    Union,
    Optional,
    Any,
    Tuple,
    Dict,
    Callable,
    Coroutine,
    Set,
    TYPE_CHECKING,
)
from pydantic import BaseModel, constr, validate_arguments

if TYPE_CHECKING:
    from roid.app import SlashCommands

from roid.exceptions import InvalidCommand
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
from roid.state import COMMAND_STATE_TARGET
from roid.callers import OptionalAsyncCallable


class CommandContext(BaseModel):
    id: Optional[str]
    type: CommandType
    name: constr(max_length=32, min_length=1)
    description: Optional[str]
    application_id: str
    guild_id: Optional[str]
    options: Optional[List[CommandOption]]
    default_permission: bool

    def __eq__(self, other: "CommandContext"):
        return (
            self.name == other.name
            and self.description == other.description
            and self.application_id == other.application_id
            and self.guild_id == other.guild_id
            and self.options == other.options
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

        # See if we have a selection options.
        # This is done in the same loop as options because it save manipulating
        # the annotations again and complicating the structure.

        # Try extract the original type from the hint.
        original = typing.get_origin(type_)
        if original is typing.Literal:
            target_type = None
            for v in typing.get_args(type_):
                if target_type is None:
                    target_type = type(v)
                elif type(v) is not target_type:
                    raise InvalidCommand(
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
                    raise InvalidCommand(
                        f"(command: {cmd_name!r}, parameter: {name!r}) enum must contain all the same types."
                    )

                choice_blocks.append(CommandChoice(name=str(e.value), value=e.value))
            type_ = target_type

        # See if its a type we recognise for conversion otherwise reject it.
        result = OPTION_TYPE_PROCESSOR.get(type_)
        if result is None:
            raise InvalidCommand(
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
            raise InvalidCommand(f"{type_!r} cannot be inferred for a choices option")

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


class Command(OptionalAsyncCallable):
    def __init__(
        self,
        app: SlashCommands,
        callback,
        name: str,
        application_id: int,
        description: Optional[str] = None,
        default_permissions: bool = False,
        guild_id: Optional[int] = None,
        guild_ids: Optional[List[int]] = None,
        cmd_type: CommandType = CommandType.CHAT_INPUT,
        defer_register: bool = True,
    ):
        super().__init__(
            callback=validate_arguments(callback),
            on_error=default_on_error,
        )

        self.app = app
        self.defer_register = defer_register

        # Sets up how we should handle special case type hints.
        # The pass_target is only valid for MESSAGE and USER commands,
        # the value will be ignored for CHAT_INPUT commands.
        #
        # We dont want to be producing options for these special cases
        # so we also remove them from the annotations.
        self._pass_target: Tuple[PassTarget, str] = (PassTarget.NONE, "_")
        self._pass_interaction: Optional[str] = None
        for param, type_ in self.annotations.copy().items():
            if type_ is Interaction:
                del self.annotations[param]
                self._pass_interaction = param
            elif type_ is PartialMessage:
                del self.annotations[param]
                self._pass_target = (PassTarget.MESSAGE, param)
            elif type_ is User:
                del self.annotations[param]
                self._pass_target = (PassTarget.USER, param)
            elif type_ is Member:
                del self.annotations[param]
                self._pass_target = (PassTarget.MEMBER, param)
            elif type_ is Interaction and self._pass_target is not None:
                raise AttributeError(
                    f"interaction is already marked to be passed to {self._pass_target!r}"
                )

        options = []
        self._defaults: Dict[str, Any] = {}

        for option, default in get_details_from_spec(name, self.spec):
            if cmd_type in (CommandType.MESSAGE, CommandType.USER):
                raise ValueError(f"only CHAT_INPUT types can have options / input")

            options.append(option)
            self._defaults[option.name] = default

            if option.choices is None:
                continue

        # Our relevant command context
        self.name = name
        self.description = description
        self.application_id = str(application_id)
        self.type = cmd_type

        if guild_id is not None and guild_ids is None:
            self.guild_ids = {
                guild_id,
            }
        elif guild_id is None and guild_ids is not None:
            self.guild_ids = set(guild_ids)
        else:
            self.guild_ids: Optional[Set[int]] = None

        self.default_permission = default_permissions
        self.options = options if len(options) != 0 else None

        self._checks_pipeline: List[CommandCheck] = []

    async def register(self, app: SlashCommands):
        """
        Register the command with the given app.

        If any guild ids are given these are registered as specific
        guild commands rather than as a global command.

        Args:
            app:
                The slash commands app which the commands
                should be registered to.
        """

        ctx = self.ctx
        if self.guild_ids is None:
            await app._http.register_command(None, ctx)
            return

        for guild_id in self.guild_ids:
            ctx.guild_id = guild_id
            await app._http.register_command(guild_id, ctx)

    @property
    def ctx(self) -> CommandContext:
        """
        Gets the general command context data.

        This is naive of any guild ids registered for this command.
        """

        return CommandContext(
            application_id=self.application_id,
            type=self.type,
            name=self.name,
            description=self.description,
            default_permission=self.default_permission,
            options=self.options,
        )

    def _get_option_data(self, interaction: Interaction) -> dict:
        if interaction.data.options is None:
            return {}

        options = extract_options(interaction)

        for name, default in self._defaults.items():
            if name not in options:
                options[name] = default

        return options

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

        cmd_type = self.type
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

    async def _get_kwargs(self, interaction: Interaction) -> dict:
        kwargs = self._get_invoke_kwargs(interaction)

        if self._pass_interaction is not None:
            kwargs[self._pass_interaction] = interaction

        return kwargs

    async def __call__(self, interaction: Interaction) -> ResponsePayload:
        try:
            for check in self._checks_pipeline:
                interaction = await check(interaction)
        except Exception as e:
            return await self._invoke_error_handler(interaction, e)

        response = await self._invoke(interaction)

        if response.data.components is None:
            return response

        state = self.app.state[COMMAND_STATE_TARGET]

        # We got along and update each button with a unique id in order
        # to pass the given context to each one.
        for row_i in range(len(response.data.components)):
            for component_i in range(len(response.data.components[row_i].components)):
                reference_id = str(uuid.uuid4())
                await state.set(reference_id, response.data.component_context)
                component = response.data.components[row_i].components[component_i]

                if component.url is not None:
                    continue

                response.data.components[row_i].components[
                    component_i
                ].custom_id = f"{component.custom_id}:{reference_id}"

        return response

    def error(
        self,
        func: Callable[[Interaction, Exception], Coroutine[Any, Any, ResponsePayload]],
    ):
        """
        Maps the given error handling coroutine function to the commands general
        error handler.

        This will override the existing error callback.

        Args:
            func:
                The function callback itself, this can be either a coroutine function
                or a regular sync function (sync functions will be ran in a new
                thread.)
        """
        self._register_error_handler(func)
        return func
