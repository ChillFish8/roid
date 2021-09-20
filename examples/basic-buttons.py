"""
Here we extend out basic.py example by adding some general buttons.

We start to see some of the magic that roid provides via it's managed state system.
This will guarantee that your worker processes see the same value across them if
used otherwise if the next button interaction isn't received by the same process
you could have all sorts of issues and confusing behaviour. Using the managed
state system you can expect the same behaviour in one process or 1000 processes.
"""

"""
A very basic example as shown in the README.

This creates two text input commands, one is ran as asynchronously as a coroutine
the other is ran in a separate thread when invoked.

Its important to note that anything callable in roid (Commands, Checks and Components)
can be ran either as a coroutine or as a threaded function.
Generally it's recommended to use async functions how ever to get the most out
of the efficiency of async.

Make sure to watch out for block code though,
see https://realpython.com/python-async-features/ for more about async
"""

import os
import uvicorn

from roid import SlashCommands, Response, ResponseFlags
from roid.components import ButtonStyle

application_id = int(os.getenv("APPLICATION_ID"))
public_key = os.getenv("PUBLIC_KEY")
token = os.getenv("BOT_TOKEN")

# We create our app, this is actually just a regular ASGI app
# but with the `POST /` route reserved.
app = SlashCommands(application_id, public_key, token)


@app.command("echo", "Echo a message.")
async def wave(message: str):
    return Response(
        content=message,
        flags=ResponseFlags.EPHEMERAL,
    )


@app.button("Click Me", style=ButtonStyle.DANGER)


if __name__ == "__main__":
    # By default we dont want roid to submit the commands for every worker
    # process, this would get us rate limited too quickly.
    # Instead we explicitly enable it for the main process via
    # the '__name__ == "__main__"' block so any workers
    # uvicorn makes wont also register the commands.
    app.register_commands_on_start()

    # We use uvicorn in this example but anything that supports an ASGI app would work.
    uvicorn.run("basic:app")

