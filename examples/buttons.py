"""
Here we extend out basic.py example by adding some general buttons by making
a counter command that allows you to +1 to a counter or delete the message.

We start to see some of the magic that roid provides via it's managed state system.
This will guarantee that your worker processes see the same value across them if
used otherwise if the next button interaction isn't received by the same process
you could have all sorts of issues and confusing behaviour. Using the managed
state system you can expect the same behaviour in one process or 1000 processes.
"""


import os
import uvicorn

from roid import SlashCommands, Response, ResponseType, ButtonStyle, InvokeContext

application_id = int(os.getenv("APPLICATION_ID"))
public_key = os.getenv("PUBLIC_KEY")
token = os.getenv("BOT_TOKEN")

# We create our app, this is actually just a regular ASGI app
# but with the `POST /` route reserved.
app = SlashCommands(application_id, public_key, token)


@app.command("counter", "Count with numbers!")
async def count():
    # Make sure you're not sending a ephemeral message if you're planning to
    # delete the response later as it wont work. Roid will silently ignore the request
    # if you do it via the Response class.
    return Response(
        content="Counter: 0",
        components=[  # Each internal list represents a new ActionRow.
            [counter, delete_button]
        ],
        # Here's the really cool bit, anything you pass via component_context will be
        # sent to the component regardless of what process it's running on.
        # Note if you want to access if the response was ephemeral or the parent
        # interaction this is available via the 'ephemeral' and 'parent' keys
        # respectively, automatically.
        component_context={"count": 1},
    )


# Here we define our delete button with the label 'Click Me' and with the
# style DANGER (red). Notice how we also pass `oneshot=True`
# If oneshot is set to True the system will automatically remove any
# passed context from the parent interaction and also prevent users from
# invoking the function multiple times. Once it's ran once, it can never be
# ran again.
@app.button("Click Me", style=ButtonStyle.DANGER, oneshot=True)
async def delete_button(
    ctx: InvokeContext,
):  # This is the data passed from the Response above.

    print(f"deleting button invoked and the echo message was: {ctx['message']}")
    return Response(delete_parent=True)


# Here we define our delete button with the label '+1' and with the
# style PRIMARY (burple).
# The general idea with this button is we just increment a counter and update
# the message showing how to use the state.
@app.button("+1", style=ButtonStyle.PRIMARY)
async def counter(
    ctx: InvokeContext,
):  # This is the data passed from the Response above.

    count = ctx.get("count", 0) + 1

    return Response(
        content=f"Count: {count}",
        type=ResponseType.UPDATE_MESSAGE,  # Update / edit the message
        components=[  # We need to re add our components to this 'new message'
            [counter, delete_button]
        ],
        component_context={"count": count},  # Our state is appended to.
    )


if __name__ == "__main__":
    # By default we dont want roid to submit the commands for every worker
    # process, this would get us rate limited too quickly.
    # Instead we explicitly enable it for the main process via
    # the '__name__ == "__main__"' block so any workers
    # uvicorn makes wont also register the commands.
    app.register_commands_on_start()

    # We use uvicorn in this example but anything that supports an ASGI app would work.
    uvicorn.run("basic-buttons:app")
