import os
from enum import Enum
import uvicorn
import logging

from roid import SlashCommands, response, Embed
from roid.objects import MemberPermissions
from roid.helpers import require_user_permissions

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
@app.command("say-hello", "wave to me", guild_id=675647130647658527)
async def test(animal: TestAnimal):
    return response(
        embed=Embed(title=f"Hello, world: {animal.value}", color=0xFFFFF),
    )


@test.button(style="Primary", label="Click me", emoji="aaa")
async def test_button_click():
    ...


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
    app.submit_commands()
    uvicorn.run("app:app", port=8000, host="0.0.0.0")
