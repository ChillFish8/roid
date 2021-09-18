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

_log = logging.getLogger("roid-main")


class SlashCommands(FastAPI):
    def __init__(
        self,
        application_id: int,
        application_public_key: str,
        token: str,
        register_commands: bool = True,
        **extra,
    ):
        super().__init__(**extra)

        self.register_commands = register_commands
        self._verify_key = VerifyKey(bytes.fromhex(application_public_key))
        self._application_id = application_id
        self._token = token
        self._global_error_handlers = KNOWN_ERRORS

        self._commands: Dict[str, Command] = {}
        self._http = HttpHandler(application_id, token)

        # register the internal route and FastAPI internals.
        self.post("/", name="Interaction Events")(self.__root)
        self.on_event("startup")(self._startup)

    @property
    def application_id(self):
        return self._application_id

    async def _startup(self):
        if not self.register_commands:
            return

        # We can set the globals in bulk.
        await self.reload_global_commands()

        for command in self._commands.values():
            if command.guild_ids is None:
                continue

            await command.register(self)

    async def reload_global_commands(self):
        """
        Registers all global commands in bulk with Discord.

        Note: This will ignore any commands with a `guild_id` or `guild_ids` specified.
        """

        _log.debug("registering global commands with discord")
        await self._http.register_commands(
            [c for c in self._commands.values() if c.guild_ids is None]
        )

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

    async def __root(self, request: Request):
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
            _log.warning(f"rejecting response due to {e!r}")
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
