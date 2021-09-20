"""
A very basic example as shown in the README.

This creates two text input commands, one is ran as asynchronously as a coroutine
the other is ran in a separate thread.

Its important to note that anything callable in roid (Commands, Checks and Components)
can be ran either as a coroutine or as a threaded function.
Generally it's recommended to use async functions how ever to get the most out
of the efficiency of async.

Make sure to watch out for block code though,
see https://realpython.com/python-async-features/ for more about async
"""

import os
import uvicorn

from roid import SlashCommands, Response, ResponseFlags, Interaction, ResponseType
from roid.helpers import check, require_user_permissions, MemberPermissions

application_id = int(os.getenv("APPLICATION_ID"))
public_key = os.getenv("PUBLIC_KEY")
token = os.getenv("BOT_TOKEN")

app = SlashCommands(application_id, public_key, token, register_commands=True)


# Roid provides a helpful permissions check for you.
# By default this returns a pre-determined message when the member is missing permissions,
# but this can be changed with the `on_error` callback parameter.
# (The check raises a UserMissingPermissions error.)
@require_user_permissions(
    MemberPermissions.BAN_MEMBERS | MemberPermissions.MOVE_MEMBERS
)
@app.command(
    "test-permissions",
    "Checks if you have the 'Ban Members' and 'Move Members' permission.",
)
async def check_permissions():
    return Response(content="Success!", flags=ResponseFlags.EPHEMERAL)


# If you want to make your own version of the above you can do so with the `check`
# decorator.
async def custom_check(interaction: Interaction) -> Interaction:
    flags = MemberPermissions.ATTACH_FILES | MemberPermissions.ADD_REACTIONS

    # We must return the interaction if everything is ok.
    if interaction.member is None:
        return interaction
    if interaction.member.permissions & flags != 0:
        return interaction

    raise ValueError(
        f"You are missing the required permissions: 'Attach Files' and 'Add Reactions'"
    )


async def on_check_error(_: Interaction, error: Exception) -> Response:
    if isinstance(error, ValueError):
        return Response(content=str(error), flags=ResponseFlags.EPHEMERAL, type=ResponseType.CHANNEL_MESSAGE_WITH_SOURCE)

    # If you dont re-raise the error will be ignored.
    raise error


@check(custom_check, on_error=on_check_error)
@app.command(
    "test-permissions",
    "Checks if you have the 'Ban Members' and 'Move Members' permission.",
)
async def check_permissions():
    return Response(content="Success!", flags=ResponseFlags.EPHEMERAL)


if __name__ == "__main__":
    # We use uvicorn in this example but anything that supports an ASGI app would work.
    uvicorn.run("basic:app")
