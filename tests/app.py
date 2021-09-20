import os
import uvicorn

from roid import SlashCommands, Response, InvokeContext, ButtonStyle, ResponseType

app = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
)


@app.command("echo", "Echo a message.")
async def wave(message: str):
    # Make sure you're not sending a ephemeral message if you're planning to
    # delete the response later as it wont work. Roid will silently ignore the request
    # if you do it via the Response class.
    return Response(
        content=message,
        components=[  # Each internal list represents a new ActionRow.
            [counter, delete_button]
        ],
        # Here's the really cool bit, anything you pass via component_context will be
        # sent to the component regardless of what process it's running on.
        # Note if you want to access if the response was ephemeral or the parent
        # interaction this is available via the 'ephemeral' and 'parent' keys
        # respectively, automatically.
        component_context={"message": message},
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


# Here we define our delete button with the label 'Click Me' and with the
# style DANGER (red). Notice how we also pass `oneshot=True`
# If oneshot is set to True the system will automatically remove any
# passed context from the parent interaction and also prevent users from
# invoking the function multiple times. Once it's ran once, it can never be
# ran again.
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
        component_context={"count": count},
    )


if __name__ == "__main__":
    app.register_commands_on_start()
    uvicorn.run("app:app", port=8000)
