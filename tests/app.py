import os
from enum import Enum

import uvicorn

from roid import (
    SlashCommands,
    Response,
    ResponseType,
    Embed,
    SelectValue,
)

app = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
    register_commands=True,
)


@app.command(
    "add-release-channel",
    description=(
        "Add Crunchy's release webhook to a channel of "
        "your choice to get the latest Anime release details."
    ),
    defer_register=False,
)
async def add_news_channel() -> Response:
    return Response(
        content=(f"<:exitment:717784139641651211> All done! I'll send news to "),
    )


if __name__ == "__main__":
    app.register_commands_on_start()
    uvicorn.run("app:app", port=8000)
