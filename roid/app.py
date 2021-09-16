import time

import httpx
import orjson
import logging

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from typing import Dict, List
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException

from roid.command import CommandType, Command, CommandOption
from roid import exceptions
from roid.interactions import InteractionType

COMMANDS_ADD = "https://discord.com/api/v8/applications/{application_id}/commands"


logger = logging.getLogger("roid-main")


class SlashCommands(FastAPI):
    def __init__(
            self,
            application_id: int,
            application_public_key: str,
            token: str,
            **extra):
        super().__init__(**extra)

        self._verify_key = VerifyKey(bytes.fromhex(application_public_key))
        self._application_id = application_id
        self._token = token

        self._commands: Dict[str, Command] = {}

        self.post("/", name="Interaction Events")(self.root)

    @property
    def application_id(self):
        return self._application_id

    async def root(self, request: Request):
        try:
            signature = request.headers["X-Signature-Ed25519"]
            timestamp = request.headers["X-Signature-Timestamp"]

            body = await request.body()

            self._verify_key.verify(
                b'%s%s' % (timestamp.encode(), body),
                bytes.fromhex(signature)
            )
        except (BadSignatureError, KeyError):
            raise HTTPException(status_code=401)

        data = orjson.loads(body)

        message_type = data['type']
        if message_type == InteractionType.PING:
            return {
                "type": 1
            }
        elif message_type == InteractionType.APPLICATION_COMMAND:
            ...
        elif message_type == InteractionType.MESSAGE_COMPONENT:
            ...
        raise HTTPException(status_code=400)

    def submit_commands(self):
        headers = {
            "Authorization": f"Bot {self._token}",
            "Content-Type": "application/json"
        }

        for command in self._commands.values():
            logger.info(f"submitting command: {command.ctx!r}")
            r = httpx.post(
                COMMANDS_ADD.format(application_id=self.application_id),
                headers=headers,
                data=command.ctx.json(),
            )

            try:
                r.raise_for_status()
            except httpx.HTTPStatusError:
                logger.error(f"failed to process command {r!r}")

                if r.status_code == 400:
                    data = r.json()
                    errors = data['errors']
                    message_details = ", ".join([item['message'] for item in errors['name']['_errors']])
                    raise exceptions.CommandRejected(status=400, body=message_details)
                raise exceptions.HTTPException(status=r.status_code, body=r.text)

            time.sleep(0.5)

    def command(
        self,
        name: str,
        description: str = "",
        cmd_type: CommandType = CommandType.CHAT_INPUT,
        guild_id: int = None,
        default_permissions: bool = True,
        options: List[CommandOption] = None,
    ):
        def wrapper(func):
            cmd = Command(
                callback=func,
                name=name,
                description=description,
                application_id=self.application_id,
                cmd_type=cmd_type,
                guild_id=guild_id,
                default_permissions=default_permissions,
                options=options,
            )

            self._commands[name] = cmd

            return cmd
        return wrapper
