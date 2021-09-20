import os
import uvicorn

from roid import SlashCommands, Response, ResponseFlags

application_id = int(os.getenv("APPLICATION_ID"))
public_key = os.getenv("PUBLIC_KEY")
token = os.getenv("BOT_TOKEN")

app = SlashCommands(application_id, public_key, token)


@app.command("echo", "Echo a message.")
async def wave(message: str):
    return Response(content=message, flags=ResponseFlags.EPHEMERAL)


@app.command("echo-sync", "Echo a message with threading.")
def wave_sync(message: str):
    return Response(content=message, flags=ResponseFlags.EPHEMERAL)


if __name__ == "__main__":
    app.register_commands_on_start()
    uvicorn.run("basic:app")
