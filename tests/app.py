import os
import uvicorn
import logging

from roid import SlashCommands, Interaction

logging.basicConfig(level=logging.INFO)

app = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
)


@app.command("wave", "wave to me", guild_id=675647130647658527)
async def test(interaction: Interaction):
    print(interaction)


if __name__ == '__main__':
    app.submit_commands()
    uvicorn.run("app:app", port=8000, host="0.0.0.0")