import asyncio
import functools
import inspect

from typing import Any, Callable, Coroutine, Union, Optional, Dict

from roid import Interaction


class OptionalAsyncCallable:
    def __init__(
        self,
        callback: Callable[..., Union[Any, Coroutine[Any, Any, Any]]],
        on_error: Optional[Callable[..., Union[Any, Coroutine[Any, Any, Any]]]] = None,
    ):
        self._callback_is_coro = asyncio.iscoroutinefunction(callback)
        self._callback = callback

        if on_error is not None:
            self._on_error_is_coro = asyncio.iscoroutinefunction(on_error)
        else:
            self._on_error_is_coro = False

        self._on_error = on_error
        self._spec = inspect.getfullargspec(callback)

        default_args = {}
        if self._spec.defaults is not None:
            delta = len(self._spec.args) - len(self._spec.defaults)
            default_args = dict(zip(self._spec.args[delta:], self._spec.defaults))

        self._default_args = default_args

    def _register_error_handler(
        self, func: Callable[..., Union[Any, Coroutine[Any, Any, Any]]]
    ):
        self._on_error_is_coro = asyncio.iscoroutinefunction(func)
        self._on_error = func

    @property
    def defaults(self) -> Dict[str, Any]:
        return self._default_args

    @property
    def annotations(self) -> Dict[str, Any]:
        return self._spec.annotations

    async def __call__(self, interaction: Interaction) -> Any:
        try:
            return await self._invoke(interaction)
        except Exception as e:
            if self._on_error is None:
                raise e from None
            return await self._invoke_error_handler(interaction, e)

    async def _get_kwargs(self, _interaction: Interaction) -> dict:  # noqa
        return {}

    async def _invoke(self, interaction: Interaction):
        kwargs = await self._get_kwargs(interaction)

        if self._callback_is_coro:
            return await self._callback(interaction, **kwargs)

        partial = functools.partial(self._callback, interaction, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial)

    async def _invoke_error_handler(
        self, interaction: Interaction, error: Exception
    ) -> Any:
        if self._on_error_is_coro:
            return await self._on_error(interaction, error)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._on_error, interaction, error)
