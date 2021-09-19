from __future__ import annotations

import httpx

from typing import Any, TYPE_CHECKING, List, Optional, Dict, Union

if TYPE_CHECKING:
    from roid.components import Component
    from roid.deferred import DeferredComponent
    from roid.objects import AllowedMentions
    from roid import Response, Embed, ResponseType


class RoidException(Exception):
    """The catch all for any roid exceptions which should be catchable."""


class AbortInvoke(RoidException):
    """A helper class that can be raised and caught by the system to override a response."""

    def __init__(
        self,
        content: str = None,
        *,
        embed: Embed = None,
        embeds: List[Embed] = None,
        allowed_mentions: AllowedMentions = None,
        flags: int = None,
        tts: bool = False,
        components: Optional[List[List[Union[Component, DeferredComponent]]]] = None,
        component_context: Optional[Dict[str, Any]] = None,
        response_type: Optional[ResponseType] = None,
    ):
        self.details = dict(
            content=content,
            embed=embed,
            embeds=embeds,
            allowed_mentions=allowed_mentions,
            flags=flags,
            tts=tts,
            components=components,
            component_context=component_context,
            response_type=response_type,
        )


class HTTPException(RoidException):
    """A exception raised by doing a REST call."""

    def __init__(self, response: httpx.Response, data: Any):
        self.response = response
        self.data = data

    def __str__(self):
        return f"status={self.response.status_code}, message={self.data!r}"

    @property
    def status_code(self) -> int:
        """The HTTP status code of the request"""
        return self.response.status_code


class Forbidden(HTTPException):
    """The request has been rejected due to invalid / incorrect authorization."""

    def __str__(self):
        return f"status={self.status_code} message='forbidden'"


class NotFound(HTTPException):
    """The given route was not found."""


class DiscordServerError(HTTPException):
    """An error occurred on discord's side."""


class CommandRejected(HTTPException):
    """Raised when an invalid command is set to be registered."""

    def __init__(self, status: int = 400, body: str = ""):
        self.status = status
        self.body = body

    def __str__(self):
        return f"status={self.status}, message={self.body}"


class InvalidComponent(RoidException):
    """A component is invalid for some reason."""


class ComponentAlreadyExists(InvalidComponent):
    """The component with the given unique_id already exists."""


class InvalidCommand(RoidException):
    """The command is invalid for some reason."""


class CommandAlreadyExists(InvalidCommand):
    """
    A command with the given unique name already exists
    either as a guild specific command or as a global.
    """
