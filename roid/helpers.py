from typing import Optional, Union, List, Callable

from pydantic import AnyHttpUrl, conint, validate_arguments

from roid import Interaction
from roid.command import Command
from roid.components import ButtonStyle
from roid.objects import MemberPermissions
from roid.response import ResponsePayload


@validate_arguments
def hyperlink_button(
    url: AnyHttpUrl,
    *,
    row: Optional[conint(ge=1, le=5)] = None,
    inline: bool = True,
    custom_id: Optional[str] = None,
    disabled: bool = False,
):
    """
    Adds a hyper linked button to the command.

    This is basically a shortcut for defining a button that doesnt
    get invoked by the interactions due to being a url.
    """

    def wrapper(func):
        if not isinstance(func, Command):
            raise TypeError(
                f"cannot apply hyper link button to {func!r}, "
                f"buttons can only be applied to roid.Command's.\n"
                f"Did you put the decorators the wrong way around?\n"
            )

        func.button(
            style=ButtonStyle.Link,
            row=row,
            inline=inline,
            custom_id=custom_id,
            disabled=disabled,
            url=url,
        )(func)

        return func

    return wrapper


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
    """

    def wrapper(func):
        if not isinstance(func, Command):
            raise TypeError(
                f"cannot add permissions check to {func!r}, "
                f"checks can only be applied to roid.Command's.\n"
                f"Did you put the decorators the wrong way around?\n"
            )

        # todo

        return func

    return wrapper
