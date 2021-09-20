from typing import Callable, Union, Coroutine, Any

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
    async def __call__(self, interaction: Interaction) -> Interaction:
        return await super().__call__(interaction)
