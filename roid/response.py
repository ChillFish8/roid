from enum import IntEnum
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, constr, validate_arguments

from roid.deferred import DeferredComponent
from roid.components import Component, ActionRow
from roid.objects import Embed, AllowedMentions


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
    allowed_mentions: Optional[AllowedMentions]
    flags: Optional[int]
    components: Optional[List[ActionRow]]

    # Purely internal
    component_context: Optional[dict]

    def dict(
        self,
        *,
        exclude: set = None,
        **kwargs,
    ) -> dict:
        if exclude is None:
            exclude = {"component_context"}
        else:
            exclude.add("component_context")

        return super().dict(exclude=exclude, **kwargs)


class DeferredResponsePayload(ResponseData):
    components: Optional[List[List[Union[Component, DeferredComponent]]]]

    class Config:
        arbitrary_types_allowed = True


class ResponsePayload(BaseModel):
    type: ResponseType
    data: Optional[ResponseData] = None


@validate_arguments(config={"arbitrary_types_allowed": True})
def response(
    content: str = None,
    *,
    embed: Embed = None,
    embeds: List[Embed] = None,
    allowed_mentions: AllowedMentions = None,
    flags: int = None,
    tts: bool = False,
    components: Optional[List[List[Union[Component, DeferredComponent]]]] = None,
    component_context: Optional[Dict[str, Any]] = None,
) -> DeferredResponsePayload:
    """
    A response to the given interaction.
    You need to pass an embed, embeds, content or a mixture of the 3.
    If not values are passed this will result in a ValueError.

    Args:
        content:
            The content of the message to respond with.

        embed:
            The rich embed to respond with.

        embeds:
            A list of rich embeds to respond with.

        allowed_mentions:
            An optional `AllowedMentions` object that describes what mentions to allow or suppress.

        flags:
            A set of `ResponseFlags` these are bitflags so can be
            joined via the `|` operator.

        tts:
            Indicates if the message should be sent using text-to-speech.

        components:
            A optional list of components to attach to the response.

        component_context:
            Any given state to be passed to the components on invocation.
            If you need to provide data to the component you *MUST* use this
            rather than a global variable as this guarantees synchronisation across
            processes.

            If you're only running 1 process (not advised for scaling) then you can
            ignore the above warning however, you will need to to change the code
            base if you later plan to use multi processing.

    Returns:
        A `ResponsePayload` object.
    """

    embeds = embeds or []

    if embed is not None:
        embeds.append(embed)

    return DeferredResponsePayload(
        tts=tts,
        allowed_mentions=allowed_mentions,
        flags=flags,
        embeds=embeds if embeds else None,
        content=content,
        components=components,
        component_context=component_context,
    )
