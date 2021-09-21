from __future__ import annotations

from typing import Callable, Union, Coroutine, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from roid import SlashCommands

from roid.callers import OptionalAsyncCallable
from roid.exceptions import RoidException
from roid.interactions import Interaction
from roid.response import Response

SyncOrAsyncCheck = Callable[
    [Interaction], Union[Interaction, Coroutine[Any, Any, Interaction]]
]

SyncOrAsyncCheckError = Callable[
    [Interaction, Exception], Union[Interaction, Coroutine[Any, Any, Response]]
]


class CheckError(RoidException):
    """The default exception for internal / pre-made checks."""


class CommandCheck(OptionalAsyncCallable):
    async def __call__(
        self, app: SlashCommands, interaction: Interaction
    ) -> Interaction:
        return await super().__call__(app, interaction)
