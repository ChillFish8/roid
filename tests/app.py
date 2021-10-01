import os
import logging
from typing import List

import uvicorn

from roid import (
    SlashCommands,
    Response,
    CommandsBlueprint,
    Option,
    ButtonStyle,
    InvokeContext,
)
from roid.components import SelectOption
from roid.interactions import CommandChoice
from roid.objects import CompletedOption, ChannelType, Channel
from roid.state import RedisBackend

logging.basicConfig(level=logging.INFO)

app = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
    register_commands=True,
    state_backend=RedisBackend(),
)

bp = CommandsBlueprint()


@bp.command(
    "search",
    description=(
        "Add Crunchy's release webhook to a channel of "
        "your choice to get the latest Anime release details."
    ),
    defer_register=False,
    guild_id=675647130647658527,
)
async def search(
    foo: Channel = Option(channel_types=[ChannelType.GUILD_TEXT]),
) -> Response:
    return Response(
        content=f"<:exitment:717784139641651211> All done! I'll send news to ",
        components=[[test_button]],
        component_context={"test": "ahh", "ttl": 30},
    )


@bp.button(label="test", style=ButtonStyle.PRIMARY)
async def test_button(ctx: InvokeContext):
    return Response(
        content=f"<:exitment:717784139641651211> All done! I'll send news to ",
        components=[
            [test_button.disabled()],
            test_select.with_options(SelectOption(label="ahhh", value="ahhh")),
        ],
        component_context={"ttl": 30},
    )


@bp.select(placeholder="Pick a value, any value!")
async def test_select(options: str):
    return Response(content="yay!")


app.add_blueprint(bp)
if __name__ == "__main__":
    app.register_commands_on_start()
    uvicorn.run("app:app", port=8000)
