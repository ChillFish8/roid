from __future__ import annotations

from typing import List, Union, TYPE_CHECKING, Optional, Callable, Coroutine, Any
from pydantic import validate_arguments

from roid import CommandType

if TYPE_CHECKING:
    from roid.app import SlashCommands
    from roid.components import Component
    from roid.command import Command, CommandContext
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
        self._target_name = target_name
        self._call_pipeline = call_pipeline

    def __call__(self, app: SlashCommands):
        caller = getattr(app, self._target_name)

        for params in self._call_pipeline:
            if isinstance(params, dict):
                caller = caller(**params)
            elif isinstance(params, CallDeferredAttr):
                caller = params(caller)
            else:
                caller = caller(*params)

        return caller


class DeferredComponent(DeferredAppItem):
    """A identifier type for deferring components."""


class DeferredButton(DeferredComponent):
    """A deferred component which is already set to target the button method."""

    def __init__(self, call_pipeline: List[Union[dict, list]]):
        super().__init__("button", call_pipeline)

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
        type: CommandType = CommandType.CHAT_INPUT,
        default_permissions: bool = False,
        defer_register: bool = True,
    ):
        self._initialised: Optional[Command] = None
        super().__init__(
            "command",
            [
                dict(
                    name=name,
                    description=description,
                    guild_id=guild_id,
                    guild_ids=guild_ids,
                    type=type,
                    default_permissions=default_permissions,
                    defer_register=defer_register,
                ),
                [callback],
            ],
        )

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


class CommandsBlueprint(DeferredAppItem):
    def __init__(self):
        self._commands: List[DeferredCommand] = []

    @validate_arguments
    def command(
        self,
        name: str,
        description: Optional[str] = None,
        default_permissions: bool = False,
        guild_id: Optional[int] = None,
        guild_ids: Optional[List[int]] = None,
        type: CommandType = CommandType.CHAT_INPUT,
        defer_register: bool = True,
    ):
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

            return cmd

        return wrapper
