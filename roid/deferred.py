from __future__ import annotations

from typing import List, Union, TYPE_CHECKING


if TYPE_CHECKING:
    from roid.app import SlashCommands
    from roid.components import Component


class DeferredAppItem:
    def __init__(
        self,
        target_name: str,
        call_pipeline: List[Union[dict, list]],
    ):
        self._target_name = target_name
        self._call_pipeline = call_pipeline

    def __call__(self, app: SlashCommands):
        caller = getattr(app, self._target_name)

        for params in self._call_pipeline:
            if isinstance(params, dict):
                caller = caller(**params)
            else:
                caller = caller(*params)

        return caller


class DeferredComponent(DeferredAppItem):
    """A identifier type for deferring components."""


class DeferredButton(DeferredComponent):
    """A deferred component which is already set to target the button method."""

    def __init__(self, call_pipeline: List[Union[dict, list]]):
        super().__init__("button", call_pipeline)

    def __call__(self, app: SlashCommands) -> Component:
        return super().__call__(app)
