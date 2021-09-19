import os
from enum import Enum
import uvicorn
import logging

from roid import SlashCommands, Embed, CommandType
from roid.components import ButtonStyle, InvokeContext
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
    "say-hello", "oofies", type=CommandType.CHAT_INPUT, guild_id=675647130647658527
)
async def test():
    resp = Response(
        embed=Embed(title=f"Hello, world", color=0xFFFFF),
        components=[
            [
                test_button_click,
                hyperlink(
                    "Click Me",
                    url="https://pydantic-docs.helpmanual.io/usage/types/#urls",
                ),
            ]`
        ],
    )

    return resp


@app.button(
    style=ButtonStyle.PRIMARY,
    label="Delete",
    emoji="<:CrunchyRollLogo:676087821596885013>",
    oneshot=True,
)
async def test_button_click(ctx: InvokeContext):
    # The button click will be reject next time someone clicks it
    await ctx.destroy()

    # An empty response or None results in the parent message not being touched.
    return Response(delete_parent=True)


#
#
# class TestSelect(Enum):
#     You = "You Are A Private 0"
#     Are = "You Are A Private 1"
#     A = "You Are A Private 2"
#     Pirate = "You Are A Private 3"
#
#
# @test.select(min_values=1, max_values=3)
# async def test_selection(choices: List[TestSelect]):
#     ...


if __name__ == "__main__":
    uvicorn.run("app:app", port=8000, host="0.0.0.0")
