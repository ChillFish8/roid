"""
Here's a very small example of select boxes also referred to as menus.

Here the user can run the /book command and select what page to view with the menu.
"""


import os
from enum import Enum

import uvicorn

from roid import (
    SlashCommands,
    Response,
    ResponseType,
    ButtonStyle,
    InvokeContext,
    Embed,
    SelectValue,
)

application_id = int(os.getenv("APPLICATION_ID"))
public_key = os.getenv("PUBLIC_KEY")
token = os.getenv("BOT_TOKEN")

app = SlashCommands(application_id, public_key, token)


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


@app.command("book", "Read a book")
async def book():
    embed = Embed(title="My book page 1", description=Pages.PAGE_1.value.value)

    return Response(
        embed=embed,
        components=[select],  # Select menus take up a whole action row.
    )


# Here we define our delete button with the label '+1' and with the
# style PRIMARY (burple).
# The general idea with this button is we just increment a counter and update
# the message showing how to use the state.
@app.select(placeholder="Pick a page, any page!")
async def select(
    ctx: InvokeContext,
    selected_value: Pages,
):  # This is the data passed from the Response above.

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
    uvicorn.run("selects:app")
