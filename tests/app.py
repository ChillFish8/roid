import os
import uvicorn

from roid import SlashCommands, Response, ResponseFlags

app = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
)


@app.command("echo", "Echo a message.", guild_id=675647130647658527)
async def echo(message: str):
    return Response(content=message, flags=ResponseFlags.EPHEMERAL)


@app.command("echo-sync", "Echo a message with threading.", guild_id=675647130647658527)
def echo_sync(message: str):
    return Response(content=message, flags=ResponseFlags.EPHEMERAL)


if __name__ == "__main__":
    app.register_commands_on_start()
    uvicorn.run("app:app", port=8000)
