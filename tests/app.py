import os
import uvicorn

from roid import SlashCommands, Response, ResponseFlags, InvokeContext, ButtonStyle

app = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
)


@app.command("echo", "Echo a message.", guild_id=675647130647658527)
async def echo(message: str):
    return Response(
        content=message,
        flags=ResponseFlags.EPHEMERAL,
        components=[[test]],
        component_context={"message": message},
    )


@app.button("click me", style=ButtonStyle.PRIMARY, oneshot=True)
async def test(ctx: InvokeContext):
    print(ctx)
    return Response(delete_parent=True)


if __name__ == "__main__":
    app.register_commands_on_start()
    uvicorn.run("app:app", port=8000)
