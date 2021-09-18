import time

import httpx
import orjson
import logging

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from typing import Dict, Type, Callable, Coroutine, Any, Union
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from pydantic import ValidationError, validate_arguments

from roid.command import CommandType, Command
from roid import exceptions
from roid.interactions import InteractionType, Interaction
from roid.config import API_URL
from roid.error_handlers import KNOWN_ERRORS
from roid.response import ResponsePayload

COMMANDS_ADD = f"{API_URL}/applications/{{application_id}}/commands"
GUILD_COMMANDS_ADD = (
    f"{API_URL}/applications/{{application_id}}/guilds/{{guild_id}}/commands"
)

GET_GLOBAL_COMMANDS = f"{API_URL}/applications/{{application_id}}/commands"
REMOVE_GLOBAL_COMMAND = f"{API_URL}/applications/{{application_id}}"

logger = logging.getLogger("roid-main")


class SlashCommands(FastAPI):
    def __init__(
        self, application_id: int, application_public_key: str, token: str, **extra
    ):
        super().__init__(**extra)

        self._verify_key = VerifyKey(bytes.fromhex(application_public_key))
        self._application_id = application_id
        self._token = token
        self._global_error_handlers = KNOWN_ERRORS

        self._commands: Dict[str, Command] = {}

        self.post("/", name="Interaction Events")(self._root)

    @property
    def application_id(self):
        return self._application_id

    def register_error(
        self,
        error: Type[Exception],
        callback: Callable[[Exception], ResponsePayload],
    ):
        """
        Registers a given error type to a handler.

        This means that if an error is raised by the system that matches the given
        exception type the callback will be invoked and it's response sent back.

        The traceback is not logged if this is set.

        Args:
            error:
                The error type itself, this must inherit from `Exception`.
            callback:
                The callback to handle the error and return a response.
        """

        if not issubclass(error, Exception):
            raise TypeError("error type does not inherit from `Exception`")

        self._global_error_handlers[error] = callback

    async def _root(self, request: Request):
        try:
            signature = request.headers["X-Signature-Ed25519"]
            timestamp = request.headers["X-Signature-Timestamp"]

            body = await request.body()

            self._verify_key.verify(
                b"%s%s" % (timestamp.encode(), body), bytes.fromhex(signature)
            )
        except (BadSignatureError, KeyError):
            raise HTTPException(status_code=401)

        data = orjson.loads(body)
        logging.debug(f"got payload: {data}")

        try:
            interaction = Interaction(**data)
        except ValidationError as e:
            logger.warning(f"rejecting response due to {e!r}")
            return HTTPException(status_code=422, detail=e.errors())

        if interaction.type == InteractionType.PING:
            return {"type": 1}
        elif interaction.type == InteractionType.APPLICATION_COMMAND:
            cmd = self._commands.get(interaction.data.name)
            if cmd is None:
                return HTTPException(status_code=400, detail="No command found")

            try:
                return await cmd(interaction)
            except Exception as e:
                handler = self._global_error_handlers.get(type(e))
                if handler is not None:
                    return handler(e)
                raise e

        elif interaction.type == InteractionType.MESSAGE_COMPONENT:
            ...
        raise HTTPException(status_code=400)

    def _request(
        self, method: str, path: str, headers: dict = None, **extra
    ) -> httpx.Response:
        set_headers = {
            "Authorization": f"Bot {self._token}",
        }

        if headers is not None:
            set_headers = {
                **set_headers,
                **headers,
            }

        url = f"{API_URL}/applications/{self.application_id}{path}"
        r = httpx.request(
            method,
            url,
            headers=set_headers,
            **extra,
        )
        time.sleep(0.5)

        try:
            r.raise_for_status()
        except httpx.HTTPStatusError:
            if r.status_code == 404:
                raise exceptions.HTTPException(
                    status=r.status_code,
                    body=f"Not Found: No route for url: {url!r}",
                )

            if r.status_code != 400:
                raise exceptions.HTTPException(status=r.status_code, body=r.text)

            data = r.json()
            errors = data["errors"]

            sections = []
            for location, detail in errors.items():
                message_details = ", ".join(
                    [item["message"] for item in detail["_errors"]]
                )
                sections.append(f"Error @ {location}: {message_details}")
            raise exceptions.HTTPException(status=400, body="\n".join(sections))
        return r

    def remove_old_global_commands(self):
        r = self._request("GET", "/commands")
        data = r.json()

        for cmd in data:
            if cmd["name"] in self._commands:
                continue

            _ = self._request("DELETE", f"/commands/{cmd['id']}")

    def submit_commands(self):
        self.remove_old_global_commands()

        for command in self._commands.values():
            logger.info(f"submitting command: {command.ctx!r}")

            if command.ctx.guild_id is None:
                url = f"/commands"
            else:
                url = f"/guilds/{command.ctx.guild_id}/commands"

            self._request(
                "POST",
                url,
                headers={"Content-Type": "application/json"},
                data=command.ctx.json(),
            )

    @validate_arguments
    def command(
        self,
        name: str,
        description: str = None,
        *,
        type: CommandType = CommandType.CHAT_INPUT,  # noqa
        guild_id: int = None,
        default_permissions: bool = True,
    ):
        if type in (CommandType.MESSAGE, CommandType.USER) and description is not None:
            raise ValueError(f"only CHAT_INPUT types can have a set description")

        def wrapper(func):
            cmd = Command(
                callback=func,
                name=name,
                description=description,
                application_id=self.application_id,
                cmd_type=type,
                guild_id=guild_id,
                default_permissions=default_permissions,
            )

            self._commands[name] = cmd

            return cmd

        return wrapper
