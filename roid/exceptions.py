from typing import Any

import httpx
import httpcore


class RoidException(Exception):
    """The catch all for any roid exceptions which should be catchable."""


class HTTPException(RoidException):
    """A exception raised by doing a REST call."""

    def __init__(self, response: httpx.Response, data: Any):
        self.response = response
        self.data = data

    def __str__(self):
        return f"status={self.response.status_code}, message={self.data}"

    @property
    def status_code(self) -> int:
        return self.response.status_code


class Forbidden(HTTPException):
    """The request has been rejected due to invalid / incorrect authorization."""


class NotFound(HTTPException):
    """The given route was not found."""


class DiscordServerError(HTTPException):
    """An error occurred on discord's side."""

    def __str__(self):
        return f"status={self.status_code}, message={self.data}"

    @property
    def status_code(self) -> int:
        return self.response.status_code


class CommandRejected(HTTPException):
    """Raised when an invalid command is set to be registed."""

    def __init__(self, status: int = 400, body: str = ""):
        self.status = status
        self.body = body

    def __str__(self):
        return f"status={self.status}, message={self.body}"


class InvalidCommandOptionType(RoidException):
    """The given option has being hinted as being a invalid type."""
