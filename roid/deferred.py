from __future__ import annotations

from typing import List, Union, TYPE_CHECKING, Optional, Callable, Coroutine, Any, Dict
from pydantic import constr, conint

from roid.exceptions import CommandAlreadyExists

if TYPE_CHECKING:
    from roid import CommandType
    from roid.app import SlashCommands
    from roid.components import Component, ButtonStyle
    from roid.command import Command, CommandContext, CommandGroup
    from roid.checks import CommandCheck
    from roid.response import ResponsePayload
    from roid.interactions import Interaction


class CallDeferredAttr:
    def __init__(self, attr: str, *args, **kwargs):
        self.attr = attr
        self.args = args
        self.kwargs = kwargs

    def __call__(self, caller):
        getattr(caller, self.attr)(*self.args, **self.kwargs)
        return caller


class DeferredAppItem:
    def __init__(
        self,
        target_name: str,
        call_pipeline: List[Union[dict, list, CallDeferredAttr]],
    ):
        self._initialised = None
        self._target_name = target_name
        self._call_pipeline = call_pipeline

    def __call__(self, app: SlashCommands):
        if self._initialised is not None:
            raise TypeError("deferred object already initialised")

        caller = getattr(app, self._target_name)

        for params in self._call_pipeline:
            if isinstance(params, dict):
                caller = caller(**params)
            elif isinstance(params, CallDeferredAttr):
                caller = params(caller)
            else:
                caller = caller(*params)

        self._initialised = caller
        return caller


class DeferredComponent(DeferredAppItem):
    """A identifier type for deferring components."""

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

        if self._initialised is not None:
            self._initialised.error(func)
        self._call_pipeline.append(CallDeferredAttr("error", func))

        return func


class DeferredButton(DeferredComponent):
    """A deferred component which is already set to target the button method."""

    def __init__(
        self,
        callback,
        label: str,
        style: ButtonStyle,
        *,
        custom_id: Optional[str] = None,
        disabled: bool = False,
        emoji: str = None,
        url: Optional[str] = None,
        oneshot: bool = False,
    ):

        call_pipeline = [
            dict(
                label=label,
                style=style,
                custom_id=custom_id,
                disabled=disabled,
                emoji=emoji,
                url=url,
                oneshot=oneshot,
            ),
            [callback],
        ]
        super().__init__("button", call_pipeline)

    def __call__(self, app: SlashCommands) -> Component:
        return super().__call__(app)


class DeferredSelect(DeferredComponent):
    """A deferred component which is already set to target the select method."""

    def __init__(
        self,
        callback,
        custom_id: Optional[str] = None,
        disabled: bool = False,
        placeholder: str = "Select an option.",
        min_values: int = 1,
        max_values: int = 1,
        oneshot: bool = False,
    ):
        call_pipeline = [
            dict(
                placeholder=placeholder,
                custom_id=custom_id,
                min_values=min_values,
                max_values=max_values,
                disabled=disabled,
                oneshot=oneshot,
            ),
            [callback],
        ]
        super().__init__("select", call_pipeline)

    def __call__(self, app: SlashCommands) -> Component:
        return super().__call__(app)


class DeferredCommand(DeferredAppItem):
    def __init__(
        self,
        callback,
        name: str,
        description: Optional[str] = None,
        guild_id: Optional[int] = None,
        guild_ids: Optional[List[int]] = None,
        type: Optional[CommandType] = None,
        default_permissions: bool = False,
        defer_register: bool = False,
    ):
        """
        A command like structure that creates a build pipeline
        when it's initialised by the app.

        This is useful for code organisation as it allows you to avoid circular imports
        in the structure.

        This has some limitations in the sense that only the public command fields are
        available and register() must be initialised first or a TypeError will be raised.

        todo attrs docs
        """

        attrs = dict(
            name=name,
            description=description,
            guild_id=guild_id,
            guild_ids=guild_ids,
            default_permissions=default_permissions,
            defer_register=defer_register,
        )

        if type:
            attrs["type"] = type

        super().__init__(
            "command",
            [
                attrs,
                [callback],
            ],
        )
        self._initialised: Optional[Command] = None

    @property
    def ctx(self) -> CommandContext:
        """
        Gets the general command context data.

        This is naive of any guild ids registered for this command.
        """

        return self._initialised.ctx

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

        if self._initialised is not None:
            self._initialised.add_check(check, at=at)
        self._call_pipeline.append(CallDeferredAttr("add_check", check=check, at=at))

    def register(self, app: SlashCommands):
        """
        Register the command with the given app.

        If any guild ids are given these are registered as specific
        guild commands rather than as a global command.

        Args:
            app:
                The slash commands app which the commands
                should be registered to.
        """

        if self._initialised is not None:
            return self._initialised.register(app)
        raise TypeError(f"deferred command is not initialised yet.")

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

        if self._initialised is not None:
            self._initialised.error(func)
        self._call_pipeline.append(CallDeferredAttr("error", func))

        return func

    def __call__(self, *args, **kwargs):
        if self._initialised is not None:
            return self._initialised.__call__(*args, **kwargs)
        return super().__call__(*args, **kwargs)


class DeferredGroupCommand(DeferredCommand):
    def __init__(
        self,
        callback,
        name: str,
    ):
        super().__init__(callback, name, description="Not Used")

    def register(self, app: SlashCommands):
        raise TypeError("group commands cannot be individually registered.")


class DeferredCommandGroup(DeferredAppItem):
    def __init__(
        self,
        name: str,
        description: str = None,
        *,
        guild_id: int = None,
        guild_ids: List[int] = None,
        default_permissions: bool = True,
        defer_register: bool = False,
        group_name: str = "command",
        group_description: str = "Select a sub command to run.",
    ):
        """
        Registers a command group with the given app.

        The description is required.
        If either the conditions are broken a `ValueError` is raised.

        Args:
            name:
                The name of the command. This must be unique / follow the general
                slash command rules as described in the "Application Command Structure"
                section of the interactions documentation.

            description:
                The description of the command. This can only be applied to
                `CommandType.CHAT_INPUT` commands.

            guild_id:
                The optional guild id if this is a guild specific command.

            guild_ids:
                An optional list of id's to register this command with multiple guilds.

            default_permissions:
                Whether the command is enabled by default when the app is added to a guild.

            defer_register:
                Whether or not to automatically register the command / update the command
                if needed.

                If set to `False` this will not be automatically registered / updated.

            group_name:
                The name of the parameter to label the sub commands group select as.

            group_description:
                The description of the select option for the sub commands.
        """

        attrs = dict(
            name=name,
            description=description,
            guild_id=guild_id,
            guild_ids=guild_ids,
            default_permissions=default_permissions,
            defer_register=defer_register,
            group_name=group_name,
            group_description=group_description,
        )

        super().__init__(
            "group",
            [attrs],
        )

        self._commands: Dict[str, DeferredGroupCommand] = {}
        self._initialised: Optional[CommandGroup] = None

    def __call__(self, *args, **kwargs):
        if self._initialised is not None:
            return self._initialised.__call__(*args, **kwargs)

        self._call_pipeline[0]["existing_commands"] = self._commands
        super().__call__(*args, **kwargs)

    @property
    def ctx(self) -> CommandContext:
        """
        Gets the general command context data.

        This is naive of any guild ids registered for this command.
        """

        return self._initialised.ctx

    def command(self, name: str):
        """
        Registers a command with the given app.

        The command type is always `CommandType.CHAT_INPUT`.

        Args:
            name:
                The name of the command. This must be unique / follow the general
                slash command rules as described in the "Application Command Structure"
                section of the interactions documentation.
        """

        def wrapper(func):
            if self._initialised is not None:
                return self._initialised.command(name=name)(func)

            cmd = DeferredGroupCommand(
                callback=func,
                name=name,
            )

            self._commands[name] = cmd

            return cmd

        return wrapper

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

        if self._initialised is not None:
            self._initialised.add_check(check, at=at)
        self._call_pipeline.append(CallDeferredAttr("add_check", check=check, at=at))

    def register(self, app: SlashCommands):
        """
        Register the command with the given app.

        If any guild ids are given these are registered as specific
        guild commands rather than as a global command.

        Args:
            app:
                The slash commands app which the commands
                should be registered to.
        """

        if self._initialised is not None:
            return self._initialised.register(app)
        raise TypeError(f"deferred command is not initialised yet.")

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

        if self._initialised is not None:
            self._initialised.error(func)
        self._call_pipeline.append(CallDeferredAttr("error", func))

        return func


class CommandsBlueprint:
    def __init__(self):
        self._commands: List[DeferredCommand] = []
        self._components: List[DeferredComponent] = []

    def group(
        self,
        name: str,
        description: str,
        *,
        guild_id: int = None,
        guild_ids: List[int] = None,
        default_permissions: bool = True,
        defer_register: bool = False,
        group_name: str = "command",
        group_description: str = "Select a sub command to run.",
    ):
        """
        Registers a command with the given app.

        If the command type is either `CommandType.MESSAGE` or `CommandType.USER`
        there cannot be any description however, if the command type
        is `CommandType.CHAT_INPUT` then description is required.
        If either of those conditions are broken a `ValueError` is raised.

        Args:
            name:
                The name of the command. This must be unique / follow the general
                slash command rules as described in the "Application Command Structure"
                section of the interactions documentation.

            description:
                The description of the command. This can only be applied to
                `CommandType.CHAT_INPUT` commands.

            guild_id:
                The optional guild id if this is a guild specific command.

            guild_ids:
                An optional list of id's to register this command with multiple guilds.

            default_permissions:
                Whether the command is enabled by default when the app is added to a guild.

            defer_register:
                Whether or not to automatically register the command / update the command
                if needed.

                If set to `False` this will not be automatically registered / updated.

            group_name:
                The name of the parameter to label the sub commands group select as.

            group_description:
                The description of the select option for the sub commands.
        """

        cmd = DeferredCommandGroup(
            name=name,
            description=description,
            guild_id=guild_id,
            guild_ids=guild_ids,
            default_permissions=default_permissions,
            defer_register=not defer_register,
            group_name=group_name,
            group_description=group_description,
        )

        self._commands.append(cmd)  # noqa

        return cmd

    def command(
        self,
        name: str,
        description: Optional[str] = None,
        default_permissions: bool = True,
        guild_id: Optional[int] = None,
        guild_ids: Optional[List[int]] = None,
        type: Optional[CommandType] = None,
        defer_register: bool = True,
    ):
        """
        Registers a command with the given app.

        If the command type is either `CommandType.MESSAGE` or `CommandType.USER`
        there cannot be any description however, if the command type
        is `CommandType.CHAT_INPUT` then description is required.
        If either of those conditions are broken a `ValueError` is raised.

        Args:
            name:
                The name of the command. This must be unique / follow the general
                slash command rules as described in the "Application Command Structure"
                section of the interactions documentation.

            description:
                The description of the command. This can only be applied to
                `CommandType.CHAT_INPUT` commands.

            type:
                The type of command. This determines if it's a chat input command,
                user context menu command or message context menu command.

                defaults to `CommandType.CHAT_INPUT`

            guild_id:
                The optional guild id if this is a guild specific command.

            guild_ids:
                An optional list of id's to register this command with multiple guilds.

            default_permissions:
                Whether the command is enabled by default when the app is added to a guild.

            defer_register:
                Whether or not to automatically register the command / update the command
                if needed.

                If set to `False` this will not be automatically registered / updated.
        """

        def wrapper(func):
            cmd = DeferredCommand(
                callback=func,
                name=name,
                description=description,
                default_permissions=default_permissions,
                guild_id=guild_id,
                guild_ids=guild_ids,
                type=type,
                defer_register=defer_register,
            )

            self._commands.append(cmd)

            return cmd

        return wrapper

    def button(
        self,
        label: str,
        style: ButtonStyle,
        *,
        custom_id: Optional[str] = None,
        disabled: bool = False,
        emoji: str = None,
        url: Optional[str] = None,
        oneshot: bool = False,
    ):
        """
        Attaches a button component to the given command.

        Args:
            style:
                The set button style. This can be any set style however url styles
                require the url kwarg and generally would be better off using
                the hyperlink helper decorator.

            custom_id:
                The custom button identifier. If you plan on having long running
                persistent buttons that dont require context from their parent command;
                e.g. reaction roles. You probably want to set this.

            disabled:
                If the button should start disabled or not.

            label:
                The button label / text shown on the button.

            emoji:
                The set emoji for the button. This should be a custom emoji
                not a unicode emoji (use the `label` field for that.)

            url:
                The hyperlink url, if this is set the function body is not invoked
                on click along with the `emoji` and `style` field being ignored.

            oneshot:
                If set to True this will remove the context from the store as soon
                as it's invoked for the first time. This allows you to essentially
                create one shot buttons which are invalidated after the first use.
        """

        def wrapper(func):
            cmd = DeferredButton(
                callback=func,
                label=label,
                style=style,
                custom_id=custom_id,
                disabled=disabled,
                emoji=emoji,
                url=url,
                oneshot=oneshot,
            )

            self._components.append(cmd)

            return cmd

        return wrapper

    def select(
        self,
        *,
        custom_id: Optional[
            constr(strip_whitespace=True, regex="a-zA-Z0-9", min_length=1)
        ] = None,
        disabled: bool = False,
        placeholder: str = "Select an option.",
        min_values: conint(ge=0, le=25) = 1,
        max_values: conint(ge=0, le=25) = 1,
        oneshot: bool = False,
    ):
        """
        A select menu component.

        This will occupy and entire action row so any components sharing the row
        will be rejected (done on a first come first served basis.)

        Args:
            custom_id:
                The custom button identifier. If you plan on having long running
                persistent buttons that dont require context from their parent command;
                e.g. reaction roles. You probably want to set this.

            disabled:
                If the button should start disabled or not.

            placeholder:
                The placeholder text the user sees while the menu is not focused.

            min_values:
                The minimum number of values the user must select.

            max_values:
                The maximum number of values the user can select.

            oneshot:
                If set to True this will remove the context from the store as soon
                as it's invoked for the first time. This allows you to essentially
                create one shot buttons which are invalidated after the first use.
        """

        def wrapper(func):
            cmd = DeferredSelect(
                callback=func,
                custom_id=custom_id,
                disabled=disabled,
                oneshot=oneshot,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
            )

            self._components.append(cmd)

            return cmd

        return wrapper
