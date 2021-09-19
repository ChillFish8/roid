import pprint
import re
import logging
import uuid
import inspect
import typing
from enum import Enum

try:
    import orjson as json
except ImportError:
    import json

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from typing import Dict, Type, Callable, Optional, List, Union, Literal
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from pydantic import ValidationError, validate_arguments, constr, conint

from roid.components import (
    Component,
    ComponentType,
    ButtonStyle,
    EMOJI_REGEX,
    SelectOption,
    SelectValue,
)
from roid.exceptions import CommandAlreadyExists, ComponentAlreadyExists
from roid.objects import PartialEmoji
from roid.command import CommandType, Command
from roid.interactions import InteractionType, Interaction
from roid.error_handlers import KNOWN_ERRORS
from roid.response import (
    ResponsePayload,
    ResponseType,
    ResponseData,
    Response,
)
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
            raise HTTPException(status_code=422, detail=e.errors())

        if interaction.type == InteractionType.PING:
            return {"type": ResponseType.PONG}
        elif interaction.type == InteractionType.APPLICATION_COMMAND:
            cmd = self._commands.get(interaction.data.name)
            if cmd is None:
                raise HTTPException(status_code=400, detail="No command found")

            DEFAULT_RESPONSE_TYPE = ResponseType.CHANNEL_MESSAGE_WITH_SOURCE
            return await self._invoke_with_handlers(
                cmd, interaction, DEFAULT_RESPONSE_TYPE, pass_parent=True
            )

        elif interaction.type == InteractionType.MESSAGE_COMPONENT:
            if interaction.data.custom_id is None:
                raise HTTPException(status_code=400)

            custom_id, *_ = interaction.data.custom_id.split(":", maxsplit=1)

            component = self._components.get(custom_id)
            if component is None:
                raise HTTPException(status_code=400, detail="No component found")

            DEFAULT_RESPONSE_TYPE = ResponseType.UPDATE_MESSAGE
            return await self._invoke_with_handlers(
                component, interaction, DEFAULT_RESPONSE_TYPE
            )

        raise HTTPException(status_code=400)

    async def _invoke_with_handlers(
        self,
        callback,
        interaction: Interaction,
        default_response_type: ResponseType,
        pass_parent: bool = False,
    ) -> ResponsePayload:
        try:
            resp = await callback(interaction)
        except Exception as e:
            handler = self._global_error_handlers.get(type(e))
            if handler is None:
                raise e from None
            resp = handler(e)

        args = [default_response_type, resp]
        if pass_parent:
            args.append(interaction)

        resp = await self.process_response(*args)
        _log.debug("returning response: %s", resp)
        return resp

    @validate_arguments(config={"arbitrary_types_allowed": True})
    async def process_response(
        self,
        default_response_type: ResponseType,
        response: Union[
            None,
            ResponsePayload,
            Response,
            ResponseData,
        ],
        parent_interaction: Optional[Interaction] = None,
    ) -> ResponsePayload:
        """
        Converts any of the possible response types into a ResponsePayload.

        This is mostly useful for deferred components and allowing some level
        of dynamic handling for users.

        Args:
            default_response_type:
                The default ResponseType to use if the Response object / data
                has not been set one.

            response:
                A given instance of the possible response types to process and
                convert.

            parent_interaction:
                The interaction a given component belongs to.
        Returns:
            A ResponsePayload instance that has had all deferred components
            resolved.
        """
        if response is None:
            return await Response().into_response_payload(
                app=self,
                default_type=default_response_type,
                parent_interaction=parent_interaction,
            )

        if isinstance(response, ResponsePayload):
            return response

        if isinstance(response, Response):
            return await response.into_response_payload(
                app=self,
                default_type=default_response_type,
                parent_interaction=parent_interaction,
            )
        elif isinstance(response, ResponseData):
            return ResponsePayload(type=default_response_type, data=response)

        raise TypeError(
            f"expected either: {ResponsePayload!r}, "
            f"{ResponseData!r} or {Response!r} return type."
        )

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
            constr(
                strip_whitespace=True, regex="a-zA-Z0-9", min_length=1, max_length=32
            )
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

        if url is not None:
            custom_id = None

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

            if url is None:
                if custom_id in self._components:
                    raise ComponentAlreadyExists(
                        f"component with custom_id {custom_id!r} has "
                        f"already been defined and registered"
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

        if max_values < min_values:
            raise ValueError(
                f"the minimum amount of select values cannot be "
                f"larger than the max amount of select values."
            )

        def wrapper(func):
            spec = inspect.getfullargspec(func)

            for param, hint in spec.annotations.items():
                if hint is Interaction:
                    continue

                origin = typing.get_origin(hint)

                # Needed if it's a multi-valued select.
                if origin is not list and max_values != 1 and min_values != 1:
                    raise TypeError(
                        f"multi-value selects must be typed as a List[T] rather than T."
                    )

                options = _get_select_options(
                    typing.get_args(hint)[0] if origin is list else hint
                )
                if len(options) == 0:
                    raise ValueError(f"Select options must contain at least one value.")

                break
            else:
                raise TypeError(
                    "function missing select value parameter and type hints."
                )

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
                options=options,
                options_parameter=param,
            )

            if custom_id in self._components:
                raise ComponentAlreadyExists(
                    f"component with custom_id {custom_id!r} has already been defined and registered"
                )
            self._components[custom_id] = component

            return component

        return wrapper


def _get_select_options(val: typing.Any) -> List[SelectOption]:
    option_choices = []
    if typing.get_origin(val) is Literal:
        for value in typing.get_args(val):
            if not isinstance(value, str):
                raise TypeError(
                    f"select options have incompatible types. "
                    f"Literals must be all type `str`. "
                    f"Expected type str found {type(value)!r}"
                )

            option = SelectOption(
                label=value,
                value=value,
            )

            if option in option_choices:
                raise ValueError(f"select options cannot have duplicate labels.")

            option_choices.append(option)
        return option_choices

    if not issubclass(val, Enum):
        raise TypeError("invalid type given expected a subclass of Enum or Literal.")

    set_type = None
    for v in val:
        if not isinstance(v.value, (str, SelectValue)):
            raise TypeError(
                f"select options have incompatible types. "
                f"enum must contain all `str` types or `SelectValue` types. "
                f"Found {type(v.value)!r}"
            )

        if (set_type is not None) and (type(v.value) is not set_type):
            raise TypeError(
                f"enum values must all be the same type. "
                f"Expected type: {set_type!r} got {type(v.value)!r}"
            )
        else:
            set_type = type(v.value)

        if isinstance(v.value, SelectValue):
            value = v.value
            option = SelectOption(
                label=value.label,
                value=value.value,
                emoji=value.emoji,
                description=value.description,
                default=value.default,
            )
        else:
            option = SelectOption(
                label=v.value,
                value=v.value,
            )

        if option in option_choices:
            raise ValueError(f"select options cannot have duplicate labels.")

        option_choices.append(option)
    return option_choices
