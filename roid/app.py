import orjson
import logging

try:
    import orjson as json
except ImportError:
    import json

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from typing import Dict, Type, Callable
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from pydantic import ValidationError, validate_arguments

from roid.command import CommandType, Command, CommandContext
from roid.interactions import InteractionType, Interaction
from roid.config import API_URL
from roid.error_handlers import KNOWN_ERRORS
from roid.response import ResponsePayload
from roid.http import HttpHandler

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
        self._http = HttpHandler(application_id, token)

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
                raise e from None

        elif interaction.type == InteractionType.MESSAGE_COMPONENT:
            ...
        raise HTTPException(status_code=400)

    def remove_old_global_commands(self, registered: Dict[str, CommandContext]):
        for cmd in registered.values():
            if cmd.name in self._commands:
                continue

            _ = self._request("DELETE", f"/commands/{cmd.id}")

    def get_commands(self) -> Dict[str, CommandContext]:
        r = self._request("GET", "/commands")
        return {data["name"]: CommandContext(**data) for data in r.json()}

    def submit_commands(self):
        registered = self.get_commands()
        self.remove_old_global_commands(registered)

        for command in self._commands.values():
            if not command.defer_register:
                continue

            command.register()

    @validate_arguments
    def command(
        self,
        name: str,
        description: str = None,
        *,
        type: CommandType = CommandType.CHAT_INPUT,  # noqa
        guild_id: int = None,
        default_permissions: bool = True,
        defer_register: bool = False,
    ):
        """
        Registers a command with the given app.

        If the command type is either `CommandType.MESSAGE` or `CommandType.USER`
        there cannot be any description however, if the command type
        is `CommandType.CHAT_INPUT` then description is required.
        If either of those conditions are broken a `ValueError` is raised.

        Args:
            name:
                The name of the command. This must be unique / follow the general
                slash command rules as described in the "Application Command Structure"
                section of the interactions documentation.

            description:
                The description of the command. This can only be applied to
                `CommandType.CHAT_INPUT` commands.

            type:
                The type of command. This determines if it's a chat input command,
                user context menu command or message context menu command.

                defaults to `CommandType.CHAT_INPUT`

            guild_id:
                The optional guild id if this is a guild specific command.

            default_permissions:
                Whether the command is enabled by default when the app is added to a guild.

            defer_register:
                Whether or not to automatically register the command / update the command
                if needed.

                If set to `False` this will not be automatically registered / updated.
        """
        if type in (CommandType.MESSAGE, CommandType.USER) and description is not None:
            raise ValueError(f"only CHAT_INPUT types can have a set description.")
        elif type is CommandType.CHAT_INPUT and description is None:
            raise ValueError(
                f"missing required field 'description' for CHAT_INPUT commands."
            )

        def wrapper(func):
            cmd = Command(
                callback=func,
                name=name,
                description=description,
                application_id=self.application_id,
                cmd_type=type,
                guild_id=guild_id,
                default_permissions=default_permissions,
                defer_register=not defer_register,
            )

            self._commands[name] = cmd

            return cmd

        return wrapper
