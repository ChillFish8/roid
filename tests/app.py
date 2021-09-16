import os
import uvicorn
import logging

from roid import SlashCommands
from roid.objects import Channel, Member

logging.basicConfig(level=logging.INFO)

app = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
)


@app.command("say-hello", "wave to me", guild_id=675647130647658527)
async def test(message: str, user: Member, channel: Channel):
    print(message, user, channel)


if __name__ == "__main__":
    app.submit_commands()
    uvicorn.run("app:app", port=8000, host="0.0.0.0")
