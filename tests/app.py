import os
from enum import Enum
from typing import List, Literal

import uvicorn
import logging

from roid import SlashCommands, Embed, CommandType, SelectValue
from roid.components import ButtonStyle
from roid.objects import MemberPermissions
from roid.helpers import require_user_permissions, hyperlink
from roid.response import Response

logging.basicConfig(level=logging.INFO)

app = SlashCommands(
    641590528026083338,
    "afca14022e5fa694a843b07699e9dd2c3fb0702ccc55cbb38c343c56aa8857bc",
    os.getenv("TOKEN"),
)


class TestAnimal(Enum):
    Cow = "Cow"
    Pig = "Pig"


@require_user_permissions(MemberPermissions.ADMINISTRATOR)
@app.command(
    "say-hello",
    "oofies",
    type=CommandType.CHAT_INPUT,
    guild_id=675647130647658527,
)
async def test():
    print("being called again")

    resp = Response(
        embed=Embed(title=f"Hello, world", color=0xFFFFF),
        components=[
            [
                delete_button,
                hyperlink(
                    "Click Me",
                    url="https://pydantic-docs.helpmanual.io/usage/types/#urls",
                ),
            ],
            [test_selection],
        ],
    )

    return resp


@app.button(
    style=ButtonStyle.PRIMARY,
    label="Delete",
    oneshot=True,
)
async def delete_button():
    # An empty response or None results in the parent message not being touched.
    return Response(delete_parent=True)


class TestSelect(Enum):
    You = SelectValue("Pick me!")
    Are = SelectValue("Or me!")
    A = SelectValue("Or mee!")
    Pirate = SelectValue("Or meee!")


@app.select(min_values=1, max_values=3)
async def test_selection(choices: List[TestSelect]):
    print(choices)
    return Response(delete_parent=True)


if __name__ == "__main__":
    uvicorn.run("app:app", port=8000, host="0.0.0.0")
