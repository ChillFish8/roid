from __future__ import annotations

from functools import reduce
from operator import or_
from typing import Optional, Union, List, Callable, TYPE_CHECKING

from pydantic import validate_arguments

if TYPE_CHECKING:
    from roid.app import SlashCommands

from roid.checks import (
    SyncOrAsyncCheckError,
    SyncOrAsyncCheck,
    CommandCheck,
    CheckError,
)
from roid.command import Command
from roid.components import ButtonStyle
from roid.objects import MemberPermissions
from roid.response import ResponsePayload
from roid.interactions import Interaction


def _null():
    pass


class DeferredAppItem:
    def __init__(
        self,
        target_name: str,
        call_pipeline: List[Union[dict, list]],
    ):
        self._target_name = target_name
        self._call_pipeline = call_pipeline

    def __call__(self, app: SlashCommands):
        caller = getattr(app, self._target_name)

        for params in self._call_pipeline:
            if isinstance(params, dict):
                caller = caller(**params)
            else:
                caller = caller(*params)

        return caller


@validate_arguments
def hyperlink(
    label: str,
    *,
    url: str,
    disabled: bool = False,
):
    """
    Adds a hyper linked button.

    This is a shortcut to defining a button with an empty body.

    Args:
        label:
            The button label, this will be the message displayed on the hyperlink.
            e.g. "Click Me!"

        url:
            The url to take the user to when they the button.

        disabled:
            If the button should be disabled or not. (If it can be clicked or not.)
    """

    return DeferredAppItem(
        "button",
        call_pipeline=[
            dict(
                style=ButtonStyle.Link,
                disabled=disabled,
                label=label,
                url=url,
            ),
            [_null],
        ],
    )


@validate_arguments
def check(cb: SyncOrAsyncCheck, on_reject: Optional[SyncOrAsyncCheckError] = None):
    """
    Creates a command check for a given function with a optional rejection catcher.

    This is automatically applied to the command being targeted.

    Args:
        cb:
            The callback to be invoked to do the check itself.
        on_reject:
            The optional callback that is invoked should the check fail.
            If this is present the response returned will be sent instead
            of anything else.

    """

    def wrapper(func: Command) -> SyncOrAsyncCheck:
        if not isinstance(func, Command):
            raise TypeError(
                f"cannot add check to {func!r}, "
                f"checks can only be applied to roid.Command's.\n"
                f"Did you put the decorators the wrong way around?\n"
            )

        func.add_check(CommandCheck(cb, on_reject))

        return func

    return wrapper


class UserMissingPermissions(CheckError):
    """
    Raised when a user does not have the required permissions flags.
    """

    def __init__(self, message: str):
        """
        Raised when a user does not have the required permissions flags.

        Args:
            message:
                The message to be returned back to the user.
        """
        self.message = message


@validate_arguments
def require_user_permissions(
    flags: Union[int, List[MemberPermissions]],
    on_reject: Optional[Callable[[Interaction], ResponsePayload]] = None,
):
    """
    Requires the user has x permissions in order to invoke the command.

    If the user does not have the required permissions then the on_reject function
    will be invoked if not set to None otherwise, the default rejection handler
    is used.

    Args:
        flags:
            The given permission flags. This can either be a integer representing
            the flags or a list of MemberPermissions (Which will be implicitly converted)
        on_reject:
            The callback to be invoked should the check fail, if this is None the
            callback is ignore.

            If this is not None then the interaction data is passed.
    """

    if isinstance(flags, list):
        flags = reduce(or_, map(lambda x: x.value, flags))

    def wrapper(func):
        if not isinstance(func, Command):
            raise TypeError(
                f"cannot add permissions check to {func!r}, "
                f"checks can only be applied to roid.Command's.\n"
                f"Did you put the decorators the wrong way around?\n"
            )

        def _permission_check(interaction: Interaction):
            if interaction.member is None:
                return interaction
            if interaction.member.permissions & flags != 0:
                return interaction

            missing: List[str] = []
            for e in MemberPermissions:
                if (e.value & flags != 0) and (
                    interaction.member.permissions & flags == 0
                ):
                    missing.append(repr(e.name.replace("_", " ").title()))
            raise UserMissingPermissions(
                f"You are missing the required permissions: {', '.join(missing)}"
            )

        check(_permission_check, on_reject)(func)

        return func

    return wrapper
