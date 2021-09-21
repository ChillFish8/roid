import os
import logging

import uvicorn

from roid import (
    SlashCommands,
    Response,
)

logging.basicConfig(level=logging.INFO)

sc = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
    register_commands=True,
)


@sc.command(
    "add-release-channel",
    description=(
        "Add Crunchy's release webhook to a channel of "
        "your choice to get the latest Anime release details."
    ),
    defer_register=False,
    guild_id=675647130647658527,
)
async def add_news_channel(app: SlashCommands) -> Response:
    return Response(
        content=(f"<:exitment:717784139641651211> All done! I'll send news to "),
    )


if __name__ == "__main__":
    sc.register_commands_on_start()
    uvicorn.run("app:sc", port=8000)
