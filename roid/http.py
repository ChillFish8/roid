from __future__ import annotations

import httpx
import asyncio
import sys
import logging
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

from pydantic import BaseModel

try:
    import orjson as json
except ImportError:
    import json

if TYPE_CHECKING:
    from roid.command import Command

from roid import __version__
from roid.exceptions import HTTPException, DiscordServerError, Forbidden, NotFound

DISCORD_DOMAIN = "discord.com"
DISCORD_CDN_DOMAIN = "cdn.discord.com"

_log = logging.getLogger("roid-http")


class MaybeUnlock:
    def __init__(self, lock: asyncio.Lock) -> None:
        self.lock = lock
        self._unlock: bool = True

    def __enter__(self) -> "MaybeUnlock":
        return self

    def defer(self) -> None:
        self._unlock = False

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._unlock:
            self.lock.release()


def _parse_rate_limit_header(response: httpx.Response) -> float:
    reset_after = response.headers.get("X-Ratelimit-Reset-After")
    if not reset_after:
        now = datetime.utcnow()
        reset = datetime.utcfromtimestamp(float(response.headers["X-Ratelimit-Reset"]))
        return (reset - now).total_seconds()
    else:
        return float(reset_after)


class HttpHandler:
    def __init__(
        self,
        application_id: int,
        token: str,
    ):
        self.lock = asyncio.Lock()
        self.client = httpx.AsyncClient(http2=True)

        python_version = sys.version_info
        self.user_agent = (
            f"DiscordBot (https://github.com/chillfish8/roid {__version__}) "
            f"Python/{python_version[0]}.{python_version[1]} "
            f"httpx/{httpx.__version__}"
        )

        self.application_id = application_id
        self.__token = token
        self._primary_route = f"https://{DISCORD_DOMAIN}/applications/{application_id}"

    async def register_command(self, guild_id: Optional[int], ctx: BaseModel):
        if guild_id is None:
            url = "/commands"
        else:
            url = f"guilds/{guild_id}/commands"

        await self.request(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            data=ctx.json(),
        )

    async def register_commands(self, commands: List[Command]):
        await self.request(
            "PUT",
            "/commands",
            headers={"Content-Type": "application/json"},
            data=json.dumps([c.ctx for c in commands]),
        )

    async def get_global_commands(self) -> List[dict]:
        return await self.request("GET", "/commands")

    async def request(self, method: str, section: str, headers: dict = None, **extra):
        set_headers = {
            "Authorization": f"Bot {self.__token}",
            "User-Agent": self.user_agent,
        }

        if headers is None:
            set_headers = {**headers, **set_headers}

        url = f"{self._primary_route}{section}"

        await self.lock.acquire()
        with MaybeUnlock(self.lock) as lock:
            for tries in range(5):
                try:
                    r = await self.client.request(
                        method, url, headers=set_headers, **extra
                    )

                    data = await r.aread()
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        data = data.decode("utf-8")

                    if r.status_code >= 500:
                        raise DiscordServerError(r, data.decode("utf-8"))

                    remaining = r.headers.get("X-Ratelimit-Remaining")
                    if remaining == "0" and r.status_code != 429:
                        # we've depleted our current bucket
                        delta = _parse_rate_limit_header(r)
                        _log.debug(
                            f"we've emptied our rate limit bucket on endpoint: {url}, retry: {delta:.2}"
                        )
                        lock.defer()
                        asyncio.get_running_loop().call_later(delta, self.lock.release)

                    if 300 > r.status_code >= 200:
                        _log.debug(f"{method} {url} successful response: {data}")
                        return data

                    if r.status_code == 429:
                        if not r.headers.get("Via") or isinstance(data, str):
                            # Cloudflare banned, maybe.
                            raise HTTPException(r, data)

                        # sleep a bit
                        retry_after: float = data["retry_after"]  # noqa
                        message = f"We are being rate limited. Retrying in {retry_after:.2} seconds."
                        _log.warning(message)

                        is_global = data.get("global", False)
                        if is_global:
                            _log.warning(
                                "Global rate limit has been hit. Retrying in %.2f seconds.",
                                retry_after,
                            )

                        await asyncio.sleep(retry_after)
                        _log.debug(
                            "Rate limit wait period has elapsed. Retrying request."
                        )

                        continue

                    if r.status_code == 403:
                        raise Forbidden(r, data)
                    elif r.status_code == 404:
                        raise NotFound(r, data)
                    elif r.status_code == 400:
                        errors = data["errors"]

                        sections = []
                        for location, detail in errors.items():
                            message_details = ", ".join(
                                [item["message"] for item in detail["_errors"]]
                            )
                            sections.append(f"Error @ {location}: {message_details}")
                        raise HTTPException(r, data="\n".join(sections))
                    else:
                        raise HTTPException(r, data)

                # An exception has occurred at the transport layer e.g. socket interrupt.
                except httpx.TransportError as e:
                    if tries < 4:
                        _log.warning(
                            f"failed preparing to retry connection failure due to error {e!r}"
                        )
                        await asyncio.sleep(1 + tries * 2)
                        continue
                    raise
                finally:
                    r.close()

            if r is not None:
                # We've run out of retries, raise.
                if r.status_code >= 500:
                    raise DiscordServerError(r, data)

                raise HTTPException(r, data)

            raise RuntimeError("Unreachable code in HTTP handling")
