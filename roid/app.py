import re
import logging
import uuid

from roid.components import Component, ComponentType, ButtonStyle, EMOJI_REGEX
from roid.exceptions import CommandAlreadyExists, ComponentAlreadyExists
from roid.objects import PartialEmoji

try:
    import orjson as json
except ImportError:
    import json

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from typing import Dict, Type, Callable, Optional, List
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from pydantic import ValidationError, validate_arguments, constr, conint

from roid.command import CommandType, Command
from roid.interactions import InteractionType, Interaction
from roid.error_handlers import KNOWN_ERRORS
from roid.response import ResponsePayload
from roid.http import HttpHandler
from roid.state import StorageBackend, MultiManagedState, SqliteBackend

_log = logging.getLogger("roid-main")


class SlashCommands(FastAPI):
    """
    A slash commands application.

    This wraps the standard FastAPI class so this can in theory be used to create
    a basic general web application around the bot as well. However, the `/` route
    is reserved and docs are disabled.
    """

    def __init__(
        self,
        application_id: int,
        application_public_key: str,
        token: str,
        register_commands: bool = True,
        state_backend: Optional[StorageBackend] = None,
        **extra,
    ):
        """
        A slash commands application.

        This wraps the standard FastAPI class so this can in theory be used to create
        a basic general web application around the bot as well. However, the `/` route
        is reserved and docs are disabled.

        Args:
            application_id:
                The application id obtained from discord.
                See (https://discord.com/developers/application) to get this.

            application_public_key:
                The public key for request verification.
                See (https://discord.com/developers/application) to get this.

            token:
                The bot token, this can be found in the portal at
                 https://discord.com/developers/applications/656598065532239892/bot.

            register_commands:
                An optional bool determining if the system automatically registers the
                new commands.

                Defaults to True.

                WARNING: If this is True it will bulk overwrite the existing
                application global commands and guild commands.

            state_backend:
                The given storage backend to use for internal state management
                and `SlashCommands.state` calls.

                If no backend is given the Sqlite backend is used.
        """

        super().__init__(**extra, docs_url=None, redoc_url=None)

        if state_backend is None:
            state_backend = SqliteBackend(f"__internal_managed_state")

        self.__state_backend = state_backend
        self.__state: Optional[MultiManagedState] = None

        self.register_commands = register_commands
        self._verify_key = VerifyKey(bytes.fromhex(application_public_key))
        self._application_id = application_id
        self._token = token
        self._global_error_handlers = KNOWN_ERRORS

        self._commands: Dict[str, Command] = {}
        self._components: Dict[str, Component] = {}
        self._http = HttpHandler(application_id, token)

        # register the internal route and FastAPI internals.
        self.post("/", name="Interaction Events")(self.__root)
        self.on_event("startup")(self._startup)
        self.on_event("shutdown")(self._shutdown)

    @property
    def state(self) -> MultiManagedState:
        return self.__state

    @state.setter
    def state(self, _):
        if hasattr(self, "_ignored_child"):
            raise RuntimeError("state cannot be set at runtime.")
        self._ignored_child = True

    @property
    def application_id(self):
        return self._application_id

    async def _startup(self):
        """A startup lifetime task invoked by the ASGI server."""

        self.__state = MultiManagedState(backend=self.__state_backend)
        await self.__state.startup()

        if not self.register_commands:
            return

        # We can set the globals in bulk.
        await self.reload_global_commands()

        for command in self._commands.values():
            if command.guild_ids is None:
                continue

            _log.info(
                f"Registering command {command.name} for guilds: {command.guild_ids}"
            )
            await command.register(self)

    async def _shutdown(self):
        """A shutdown lifetime task invoked by the ASGI server."""

        try:
            await self._http.shutdown()
        finally:
            await self.__state.shutdown()

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

        data = json.loads(body)
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
            if interaction.data.custom_id is None:
                return HTTPException(status_code=400)

            custom_id, *_ = interaction.data.custom_id.split(":", maxsplit=1)

            component = self._components.get(custom_id)
            if component is None:
                return HTTPException(status_code=400, detail="No component found")

            try:
                return await component(interaction)
            except Exception as e:
                handler = self._global_error_handlers.get(type(e))
                if handler is not None:
                    return handler(e)
                raise e from None

        raise HTTPException(status_code=400)

    @validate_arguments
    def command(
        self,
        name: str,
        description: str = None,
        *,
        type: CommandType = CommandType.CHAT_INPUT,  # noqa
        guild_id: int = None,
        guild_ids: List[int] = None,
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

            guild_ids:
                An optional list of id's to register this command with multiple guilds.

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
                app=self,
                callback=func,
                name=name,
                description=description,
                application_id=self.application_id,
                cmd_type=type,
                guild_id=guild_id,
                guild_ids=guild_ids,
                default_permissions=default_permissions,
                defer_register=not defer_register,
            )

            if name in self._commands:
                raise CommandAlreadyExists(
                    f"command with name {name!r} has already been defined and registered"
                )
            self._commands[name] = cmd

            return cmd

        return wrapper

    @validate_arguments
    def button(
        self,
        label: str,
        style: ButtonStyle,
        *,
        custom_id: Optional[
            constr(strip_whitespace=True, regex="a-zA-Z0-9", min_length=1)
        ] = None,
        disabled: bool = False,
        emoji: constr(strip_whitespace=True, regex=EMOJI_REGEX) = None,
        url: Optional[str] = None,
        oneshot: bool = False,
    ):
        """
        Attaches a button component to the given command.

        Args:
            style:
                The set button style. This can be any set style however url styles
                require the url kwarg and generally would be better off using
                the hyperlink helper decorator.

            custom_id:
                The custom button identifier. If you plan on having long running
                persistent buttons that dont require context from their parent command;
                e.g. reaction roles. You probably want to set this.

            disabled:
                If the button should start disabled or not.

            label:
                The button label / text shown on the button.

            emoji:
                The set emoji for the button. This should be a custom emoji
                not a unicode emoji (use the `label` field for that.)

            url:
                The hyperlink url, if this is set the function body is not invoked
                on click along with the `emoji` and `style` field being ignored.

            oneshot:
                If set to True this will remove the context from the store as soon
                as it's invoked for the first time. This allows you to essentially
                create one shot buttons which are invalidated after the first use.
        """

        if emoji is not None:
            emoji = re.findall(EMOJI_REGEX, emoji)[0]
            animated, name, id_ = emoji
            emoji = PartialEmoji(id=id_, name=name, animated=bool(animated))

        if custom_id is None:
            custom_id = str(uuid.uuid4())

        def wrapper(func):
            component = Component(
                app=self,
                callback=func,
                type_=ComponentType.BUTTON,
                style=style,
                custom_id=custom_id,
                disabled=disabled,
                label=label,
                emoji=emoji,
                url=url,
                oneshot=oneshot,
            )

            if custom_id in self._components:
                raise ComponentAlreadyExists(
                    f"component with custom_id {custom_id!r} has already been defined and registered"
                )
            self._components[custom_id] = component

            return component

        return wrapper

    @validate_arguments
    def select(
        self,
        *,
        custom_id: Optional[
            constr(strip_whitespace=True, regex="a-zA-Z0-9", min_length=1)
        ] = None,
        disabled: bool = False,
        placeholder: str = "Select an option.",
        min_values: conint(ge=0, le=25) = 1,
        max_values: conint(ge=0, le=25) = 1,
        oneshot: bool = False,
    ):
        """
        A select menu component.

        This will occupy and entire action row so any components sharing the row
        will be rejected (done on a first come first served basis.)

        Args:
            custom_id:
                The custom button identifier. If you plan on having long running
                persistent buttons that dont require context from their parent command;
                e.g. reaction roles. You probably want to set this.

            disabled:
                If the button should start disabled or not.

            placeholder:
                The placeholder text the user sees while the menu is not focused.

            min_values:
                The minimum number of values the user must select.

            max_values:
                The maximum number of values the user can select.

            oneshot:
                If set to True this will remove the context from the store as soon
                as it's invoked for the first time. This allows you to essentially
                create one shot buttons which are invalidated after the first use.
        """

        if custom_id is None:
            custom_id = str(uuid.uuid4())

        def wrapper(func):
            component = Component(
                app=self,
                callback=func,
                type_=ComponentType.SELECT_MENU,
                custom_id=custom_id,
                disabled=disabled,
                placeholder=placeholder,
                min_values=min_values,
                max_values=max_values,
                oneshot=oneshot,
            )

            if custom_id in self._components:
                raise ComponentAlreadyExists(
                    f"component with custom_id {custom_id!r} has already been defined and registered"
                )
            self._components[custom_id] = component

            return component

        return wrapper
