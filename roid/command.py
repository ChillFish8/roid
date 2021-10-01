from __future__ import annotations

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
from fastapi import HTTPException


if TYPE_CHECKING:
    from roid.app import SlashCommands
    from roid.deferred import DeferredGroupCommand

from roid.exceptions import InvalidCommand, CommandAlreadyExists
from roid.interactions import (
    Interaction,
    CommandType,
    CommandOption,
    CommandOptionType,
    CommandChoice,
    InteractionType,
)
from roid.objects import (
    Role,
    Channel,
    Member,
    PartialMessage,
    User,
    ResponseType,
    CompletedOption,
    ChannelType,
)
from roid.extractors import extract_options
from roid.checks import CommandCheck
from roid.response import ResponsePayload, ResponseData
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
        autocomplete: Optional[bool],
        channel_types: Optional[List[ChannelType]],
    ):
        self.default = default
        self.required = self.default is Ellipsis
        self.name = name
        self.description = description
        self.autocomplete = autocomplete
        self.channel_types = channel_types


def Option(
    default: Union[str, int, float, None, bool] = ...,
    *,
    name: str = None,
    description: str = None,
    autocomplete: Optional[bool] = None,
    channel_types: List[ChannelType] = None,
) -> Any:  # noqa
    return SetValue(default, name, description, autocomplete, channel_types)


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


async def default_on_error(_: Interaction, exception: Exception) -> ResponsePayload:
    raise exception from None


class PassTarget(IntEnum):
    NONE = auto()
    MESSAGE = auto()
    USER = auto()
    MEMBER = auto()


class AutoCompleteHandler(OptionalAsyncCallable):
    """
    A autocomplete option that gets invoked when ever a user starts typing
    the auto complete field.
    """

    DEFAULT_TARGET = "_AUTO_COMPLETE_DEFAULT"
    Callback = Callable[
        ..., Union[List[CompletedOption], Coroutine[Any, Any, CompletedOption]]
    ]

    def __init__(
        self,
        callback: Callback,
        target: Optional[str] = None,
    ):
        super().__init__(callback)

        self.target = target

        self.target_options = {name for name in self.annotations if name != "return"}

    async def _get_kwargs(
        self,
        app: SlashCommands,
        interaction: Interaction,
    ) -> dict:
        kwargs = await super()._get_kwargs(app, interaction)

        if interaction.data.options is None:
            raise HTTPException(status_code=400)

        for option in interaction.data.options:
            if self.target is not None and self.target == option.name:
                kwargs[option.name] = option
                break

            if self.target is None and len(self.annotations) <= 1:
                kwargs[option.name] = option
            elif self.target is None and option.name in self.annotations:
                kwargs[option.name] = option

        return kwargs


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
            callback=callback,
            on_error=default_on_error,
            validate=True,
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
        for param, type_ in self.annotations.copy().items():
            if name == "return":
                continue

            if type_ is PartialMessage:
                del self.annotations[param]
                self._pass_target = (PassTarget.MESSAGE, param)
            elif type_ is User:
                del self.annotations[param]
                self._pass_target = (PassTarget.USER, param)
            elif type_ is Member:
                del self.annotations[param]
                self._pass_target = (PassTarget.MEMBER, param)

        options = []
        self._option_defaults: Dict[str, Any] = {}

        for option, default in self._get_details_from_spec(name):
            if cmd_type in (CommandType.MESSAGE, CommandType.USER):
                raise ValueError(f"only CHAT_INPUT types can have options / input")

            options.append(option)
            self._option_defaults[option.name] = default

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

        self._autocomplete_handlers: Dict[str, AutoCompleteHandler] = {}
        self._checks_pipeline: List[CommandCheck] = []

    def _get_details_from_spec(
        self,
        cmd_name: str,
    ) -> List[Tuple[CommandOption, Any]]:
        options = []
        for name, type_ in self.annotations.items():
            if name == "return":
                continue

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

                    choice_blocks.append(
                        CommandChoice(name=str(e.value), value=e.value)
                    )
                type_ = target_type

            # See if its a type we recognise for conversion otherwise reject it.
            result = OPTION_TYPE_PROCESSOR.get(type_)
            if result is None:
                raise InvalidCommand(
                    f"(command: {cmd_name!r}) type {type_!r} is not supported for command option / choice types."
                )

            option_type, description = result
            if name in self.defaults:
                default = self.defaults[name]
            else:
                default = Ellipsis

            channel_types = None
            required = default is Ellipsis
            if isinstance(default, SetValue):
                name = default.name or name
                description = default.description or description
                required = default.default is Ellipsis
                channel_types = default.channel_types
            elif len(choice_blocks) > 0:
                description = "Select an option from the list."

            kwargs = dict(
                name=name,
                description=description,
                type=option_type,
                required=required,
                channel_types=channel_types,
            )

            if (len(choice_blocks) > 0) and (option_type not in VALID_CHOICE_TYPES):
                raise InvalidCommand(
                    f"{type_!r} cannot be inferred for a choices option"
                )

            if len(choice_blocks) > 0:
                kwargs["choices"] = choice_blocks

            opt = CommandOption(**kwargs)
            options.append((opt, default))

        return options

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

        options = self.options
        if options is not None:
            for option in options:
                if (
                    (option.name in self._autocomplete_handlers)
                    and (option.autocomplete is None)
                    and (option.type == CommandOptionType.STRING)
                ):
                    option.autocomplete = True
                    continue

                general_handler = self._autocomplete_handlers.get(
                    AutoCompleteHandler.DEFAULT_TARGET
                )
                if (
                    (general_handler is not None)
                    and (option.name in general_handler.target_options)
                    and (option.autocomplete is None)
                    and (option.type == CommandOptionType.STRING)
                ):
                    option.autocomplete = True

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

        for name, default in self._option_defaults.items():
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

    async def _get_kwargs(self, app: SlashCommands, interaction: Interaction) -> dict:
        """
        Creates the kwarg dictionary for the command to be invoked based off
        of the interaction.

        If this is a non CHAT_INPUT command type the internal `pass_target`
        variable is used to determine if the targeted message / user should be
        passed directly.
        """

        kwargs = await super()._get_kwargs(app, interaction)

        extend = {}
        cmd_type = self.type
        pass_target, pass_name = self._pass_target
        if cmd_type == CommandType.CHAT_INPUT:
            extend = self._get_option_data(interaction)
        elif cmd_type == CommandType.MESSAGE and pass_target == PassTarget.MESSAGE:
            extend = {
                pass_name: interaction.data.resolved.messages[
                    interaction.data.target_id
                ]
            }
        elif cmd_type == CommandType.USER and pass_target == PassTarget.USER:
            extend = {
                pass_name: interaction.data.resolved.users[interaction.data.target_id]
            }
        elif cmd_type == CommandType.USER and pass_target == PassTarget.MEMBER:
            target_id = interaction.data.target_id
            member = interaction.data.resolved.members[target_id]
            user = interaction.data.resolved.users[target_id]
            member.user = user
            extend = {pass_name: member}

        return {**kwargs, **extend}

    async def __call__(
        self,
        app: SlashCommands,
        interaction: Interaction,
    ) -> ResponsePayload:
        if interaction.type == InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
            return await self._handle_autocomplete(app, interaction)

        try:
            for check in self._checks_pipeline:
                interaction = await check(app, interaction)
        except Exception as e:
            return await self._invoke_error_handler(app, interaction, e)

        return await self._invoke(app, interaction)

    async def _handle_autocomplete(
        self,
        app: SlashCommands,
        interaction: Interaction,
    ) -> ResponsePayload:

        primary_caller = self._autocomplete_handlers.get(
            AutoCompleteHandler.DEFAULT_TARGET
        )
        if primary_caller is not None:
            results = await primary_caller(app, interaction)
            return ResponsePayload(
                type=ResponseType.APPLICATION_COMMAND_AUTOCOMPLETE_RESULT,
                data=ResponseData(choices=results),
            )

        if interaction.data.options is None:
            raise HTTPException(status_code=400)

        target: Optional[str] = None
        for option in interaction.data.options:
            if option.focused:
                target = option.name
                break

        if target is None:
            raise HTTPException(status_code=400)

        secondary_caller = self._autocomplete_handlers.get(target)
        if secondary_caller is None:
            raise ValueError(
                f"no autocomplete handler exists option {secondary_caller!r}."
            )

        results = await secondary_caller(app, interaction)
        return ResponsePayload(
            type=ResponseType.APPLICATION_COMMAND_AUTOCOMPLETE_RESULT,
            data=ResponseData(choices=results),
        )

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

    def autocomplete(
        self,
        func: Optional[AutoCompleteHandler.Callback] = None,
        *,
        for_=AutoCompleteHandler.DEFAULT_TARGET,
    ):
        """
        Add a callback for auto complete interaction
        requests for all or a specific option.

        This decorator can be used either as a generic @command.autocomplete
        or pass a option target via @command.autocomplete(for_="my_option_name").

        Args:
            func:
                The callback for the autocomplete interaction.
                This is only required when adding a general handler for all options.
            for_:
                A optional name to target a specific option.
                If this is given the callback will only be invoked if the value is
                focused.
                The callback required will also just be given the raw `value: str`
                keyword opposed to a set of kwargs.
        """

        if func is not None:
            existing = self._autocomplete_handlers.get(for_)
            if existing:
                raise ValueError(
                    f"autocomplete handler {for_!r} registered already as callable: {existing._callback!r}."
                )

            target = for_ if for_ != AutoCompleteHandler.DEFAULT_TARGET else None
            self._autocomplete_handlers[for_] = AutoCompleteHandler(func, target=target)
            return func

        if for_ not in self.original_annotations:
            if for_ != AutoCompleteHandler.DEFAULT_TARGET:
                raise ValueError(
                    f"there is no parameter named {for_!r} in the command's signature."
                )
            raise TypeError(f"missing required keyword parameter 'for_'.")

        existing = self._autocomplete_handlers.get(AutoCompleteHandler.DEFAULT_TARGET)
        if existing:
            raise ValueError(
                f"general autocomplete handler registered already as callable: {existing._callback!r}."
            )

        def wrapper(func_):
            self._autocomplete_handlers[for_] = AutoCompleteHandler(func_, target=for_)
            return func_

        return wrapper


class GroupCommand(Command):
    def __init__(self, app: SlashCommands, callback, name: str, application_id: int):
        super().__init__(
            app, callback, name, application_id, cmd_type=CommandType.CHAT_INPUT
        )

    def register(self, app: SlashCommands):
        raise TypeError("group commands cannot be individually registered.")


class CommandGroup(Command):
    def __init__(
        self,
        app: SlashCommands,
        name: str,
        application_id: int,
        description: Optional[str] = None,
        default_permissions: bool = False,
        guild_id: Optional[int] = None,
        guild_ids: Optional[List[int]] = None,
        defer_register: bool = True,
        group_name: str = "command",
        group_description: str = "Select a sub command to run.",
        existing_commands: Dict[str, DeferredGroupCommand] = None,
    ):
        if existing_commands is not None:
            commands = {}
            for name, deferred in existing_commands.items():
                commands[name] = deferred(app=app)
            existing_commands = commands
        else:
            existing_commands = {}

        super().__init__(
            app=app,
            callback=self._group_invoker,
            application_id=application_id,
            name=name,
            description=description,
            default_permissions=default_permissions,
            guild_id=guild_id,
            guild_ids=guild_ids,
            defer_register=defer_register,
            cmd_type=CommandType.CHAT_INPUT,
        )

        self.group_name = group_name
        self.group_description = group_description

        self._commands: Dict[str, GroupCommand] = existing_commands

    async def _group_invoker(
        self, app: SlashCommands, interaction: Interaction, **kwargs
    ):
        sub_command = kwargs.pop(self.group_name)

        if interaction.data.options[0].name == self.group_name:
            interaction.data.options.pop(0)
        else:
            for i, option in enumerate(interaction.data.options):
                if option.name == self.group_name:
                    interaction.data.options.pop(i)
                    break

        return await self._commands[sub_command](app, interaction)

    @property
    def ctx(self) -> CommandContext:
        """
        Gets the general command context data.

        This is naive of any guild ids registered for this command.
        """

        if len(self._commands) == 0:
            raise ValueError(f"no sub commands registered for group.")

        ctx = super().ctx
        options = ctx.options or []

        choices = []
        for command in self._commands.values():
            choices.append(CommandChoice(name=command.name, value=command.name))

        options.append(
            CommandOption(
                type=CommandOptionType.STRING,
                name=self.group_name,
                description=self.group_description,
                choices=choices,
                required=True,
            )
        )

        ctx.options = options
        return ctx

    @validate_arguments
    def command(self, name: str):
        """
        Registers a group command with the given app.

        The command type is always `CommandType.CHAT_INPUT`.

        Args:
            name:
                The name of the command. This must be unique / follow the general
                slash command rules as described in the "Application Command Structure"
                section of the interactions documentation.
        """

        def wrapper(func):
            cmd = GroupCommand(
                app=self.app,
                callback=func,
                name=name,
                application_id=int(self.application_id),
            )

            if name in self._commands:
                raise CommandAlreadyExists(
                    f"command with name {name!r} has already been defined and registered"
                )
            self._commands[name] = cmd

            return cmd

        return wrapper
