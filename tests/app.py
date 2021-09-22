import os
import logging
from typing import List

import uvicorn

from roid import (
    SlashCommands,
    Response,
)
from roid.interactions import CommandChoice
from roid.objects import CompletedOption
from roid.command import CommandOption

logging.basicConfig(level=logging.INFO)

app = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
    register_commands=True,
)


@app.command(
    "search",
    description=(
        "Add Crunchy's release webhook to a channel of "
        "your choice to get the latest Anime release details."
    ),
    defer_register=False,
    guild_id=675647130647658527,
)
async def search(query: str) -> Response:
    print(query)
    return Response(
        content=(f"<:exitment:717784139641651211> All done! I'll send news to "),
    )


@search.autocomplete(for_="query")
async def run_query(query: CommandChoice = None):
    print(query)
    return [CompletedOption(name=query.value, value=query.value)]


if __name__ == "__main__":
    app.register_commands_on_start()
    uvicorn.run("app:app", port=8000)
