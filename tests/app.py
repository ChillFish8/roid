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


class Pages(Enum):
    PAGE_1 = SelectValue(
        "Lust: A fast, auto-optimizing image server designed for high throughput and caching.",
        label="Page 1",
    )
    PAGE_2 = SelectValue(
        "Lnx: A REST based implementation of the tantivy search engine system WIP.",
        label="Page 2",
    )
    PAGE_3 = SelectValue(
        "ReWrk: A more modern http framework benchmarker supporting HTTP/1 and HTTP/2 benchmarks.",
        label="Page 3",
    )
    PAGE_4 = SelectValue(
        "Roid: A fast, stateless http slash commands framework for scale. Built by the Crunchy bot team.",
        label="Page 4",
    )


@app.command("book", "Read a book", guild_id=675647130647658527)
async def book():
    embed = Embed(title="My book page 1", description=Pages.PAGE_1.value.value)

    return Response(
        embed=embed,
        components=[select],  # Select menus take up a whole action row.
    )


# Our select component takes the values of our enum and makes them
# into a list of selectable options.
@app.select(placeholder="Pick a page, any page!")
async def select(selected_value: Pages):

    embed = Embed(
        title=f"My book {selected_value.value.label}",
        description=selected_value.value.value,
    )

    return Response(
        embed=embed,
        type=ResponseType.UPDATE_MESSAGE,
        components=[select],
    )


if __name__ == "__main__":
    app.register_commands_on_start()
    uvicorn.run("app:app", port=8000)
