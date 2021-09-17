import asyncio
from typing import Callable, Optional, Union, Coroutine, Any

from roid.exceptions import RoidException
from roid.interactions import Interaction


SyncOrAsyncCallable = Callable[
    [Interaction], Union[Interaction, Coroutine[Any, Any, Interaction]]
]

SyncOrAsyncCallableError = Callable[
    [Interaction, Exception], Union[Interaction, Coroutine[Any, Any, Interaction]]
]


class CheckError(RoidException):
    """The default exception for internal / pre-made checks."""


class CommandCheck:
    def __init__(
        self,
        callback: SyncOrAsyncCallable,
        on_reject: Optional[SyncOrAsyncCallableError] = None,
    ):
        self._await_coroutine_cb = asyncio.iscoroutinefunction(callback)
        self._await_coroutine_or = asyncio.iscoroutinefunction(on_reject)
        self._callback = callback
        self._on_reject = on_reject

    async def __call__(self, interaction: Interaction) -> Interaction:
        try:
            result = self._callback(interaction)
            if self._await_coroutine_cb:
                return await result
            return result
        except Exception as e:
            result = self._on_reject(interaction, e)
            if self._await_coroutine_cb:
                return await result
            return result
