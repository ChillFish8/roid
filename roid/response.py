from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, constr

from roid.objects import Embed


class ResponseType(IntEnum):
    PONG = 1
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7


class ResponseFlags(IntEnum):
    EPHEMERAL = 1 << 6


class ResponseData(BaseModel):
    tts: Optional[bool]
    content: Optional[constr(min_length=1, max_length=2000, strip_whitespace=True)]
    embeds: Optional[List[Embed]]
    allowed_mentions: Optional[bool]
    flags: Optional[int]


class ResponsePayload(BaseModel):
    type: ResponseType
    data: Optional[ResponseData] = None


def response(
    content: str = None,
    *,
    embed: Embed = None,
    embeds: List[Embed] = None,
    allowed_mentions: bool = False,
    flags: int = None,
    tts: bool = False,
) -> ResponsePayload:
    embeds = embeds or []

    if embed is not None:
        embeds.append(embed)

    data = ResponseData(
        tts=tts,
        allowed_mentions=allowed_mentions,
        flags=flags,
        embeds=embeds if embeds else None,
        content=content,
    )

    return ResponsePayload(type=ResponseType.CHANNEL_MESSAGE_WITH_SOURCE, data=data)
