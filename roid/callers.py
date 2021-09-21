from __future__ import annotations

import asyncio
import functools
import inspect

from typing import Any, Callable, Coroutine, Union, Optional, Dict, TYPE_CHECKING
from pydantic import validate_arguments


if TYPE_CHECKING:
    from roid import SlashCommands
    from roid.interactions import Interaction


class OptionalAsyncCallable:
    def __init__(
        self,
        callback: Callable[..., Union[Any, Coroutine[Any, Any, Any]]],
        on_error: Optional[Callable[..., Union[Any, Coroutine[Any, Any, Any]]]] = None,
        *,
        callback_is_async: bool = False,
        validate: bool = False,
    ):
        self._callback_is_coro = callback_is_async or asyncio.iscoroutinefunction(
            callback
        )

        if on_error is not None:
            self._on_error_is_coro = asyncio.iscoroutinefunction(on_error)
        else:
            self._on_error_is_coro = False
        self._on_error = on_error

        self._pass_error_app: bool = False

        if self._on_error is not None:
            for param, hint in inspect.getfullargspec(
                self._on_error
            ).annotations.items():
                if param == "return":
                    continue

                if param == "app":
                    self._pass_error_app = True
                    del self.annotations[param]
                    break

        self.spec = inspect.getfullargspec(callback)

        self._pass_interaction_to: Optional[str] = None
        self._pass_app: bool = False
        for param, hint in self.annotations.copy().items():
            if param == "return":
                continue

            if param == "app":
                self._pass_app = True
                del self.annotations[param]
                continue

            try:
                name = hint.__name__
            except AttributeError:
                name = hint

            if name == "Interaction" and self._pass_interaction_to is None:
                self._pass_interaction_to = param
                del self.annotations[param]
            elif name == "Interaction" and self._pass_interaction_to is not None:
                raise TypeError(
                    f"check already has `Interaction` being passed to it via {self._pass_interaction_to!r}"
                )

        default_args = {}
        if self.spec.defaults is not None:
            delta = len(self.spec.args) - len(self.spec.defaults)
            default_args = dict(zip(self.spec.args[delta:], self.spec.defaults))
        self._default_args = default_args

        self._callback = (
            validate_arguments(config={"arbitrary_types_allowed": True})(callback)
            if validate
            else callback
        )

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
        return self.spec.annotations

    async def __call__(self, app: SlashCommands, interaction: Interaction) -> Any:
        try:
            return await self._invoke(app, interaction)
        except Exception as e:
            if self._on_error is None:
                raise e from None
            return await self._invoke_error_handler(app, interaction, e)

    async def _get_kwargs(
        self, app: SlashCommands, interaction: Interaction
    ) -> dict:  # noqa
        kwargs = {}

        if self._pass_interaction_to is not None:
            kwargs[self._pass_interaction_to] = interaction

        if self._pass_app:
            kwargs["app"] = app

        return kwargs

    async def _invoke(self, app: SlashCommands, interaction: Interaction):
        kwargs = await self._get_kwargs(app, interaction)

        if self._callback_is_coro:
            return await self._callback(**kwargs)

        partial = functools.partial(self._callback, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial)

    async def _invoke_error_handler(
        self,
        app: SlashCommands,
        interaction: Interaction,
        error: Exception,
    ) -> Any:
        if self._on_error_is_coro:
            if self._pass_error_app:
                return await self._on_error(app, interaction, error)
            return await self._on_error(interaction, error)

        partial = functools.partial(self._on_error, interaction, error)

        if self._pass_error_app:
            partial.keywords["app"] = app

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial)
