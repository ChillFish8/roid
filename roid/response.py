from __future__ import annotations

import uuid
from typing import List, Optional, Dict, Any, Union, TYPE_CHECKING

from pydantic import BaseModel, constr, validate_arguments

from roid.state import COMMAND_STATE_TARGET

if TYPE_CHECKING:
    from roid import Interaction
    from roid.app import SlashCommands

from roid.deferred import DeferredComponent
from roid.components import Component, ActionRow
from roid.objects import Embed, AllowedMentions, ResponseType, ResponseFlags


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


class Response:
    """
    A response to the given interaction.
    You need to pass an embed, embeds, content or a mixture of the 3.
    If not values are passed this will result in a ValueError.
    """

    @validate_arguments(config={"arbitrary_types_allowed": True})
    def __init__(
        self,
        content: str = None,
        *,
        embed: Embed = None,
        embeds: List[Embed] = None,
        allowed_mentions: AllowedMentions = None,
        flags: int = None,
        tts: bool = False,
        components: Optional[List[List[Union[Component, DeferredComponent]]]] = None,
        component_context: Optional[Dict[str, Any]] = None,
        response_type: Optional[ResponseType] = None,
        delete_parent: bool = False,
    ):
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

            delete_parent:
                Whether or not to delete the parent interaction or not.
                If set to True the parent will be deleted.

        Returns:
            A `ResponsePayload` object.
        """

        embeds = embeds or []

        if embed is not None:
            embeds.append(embed)

        self.delete_parent = delete_parent
        self.parent: Optional[Interaction] = None
        self._response_type = response_type
        self._payload = DeferredResponsePayload(
            tts=tts,
            allowed_mentions=allowed_mentions,
            flags=flags,
            embeds=embeds if embeds else None,
            content=content,
            components=components,
            component_context=component_context or {},
        )

    @property
    def is_empty(self) -> bool:
        return not (
            bool(self._payload.content)
            or bool(self._payload.embeds)
            or bool(self._payload.components)
        )

    async def into_response_payload(
        self,
        app: SlashCommands,
        default_type: ResponseType,
        parent_interaction: Optional[Interaction] = None,
    ):
        if self.delete_parent and self.is_empty:
            self._payload.content = "Deleted parent."
            self._payload.flags = ResponseFlags.EPHEMERAL
            return ResponsePayload(type=ResponseType.DEFERRED_UPDATE_MESSAGE)

        if self.is_empty:
            return ResponsePayload(type=ResponseType.DEFERRED_UPDATE_MESSAGE)

        if self._payload.components is None:
            return ResponsePayload(
                type=ResponseType.CHANNEL_MESSAGE_WITH_SOURCE, data=self._payload
            )

        state = app.state[COMMAND_STATE_TARGET]

        action_rows = []
        components = self._payload.components
        for block in components:
            component_block = []
            for c in block:
                if not isinstance(c, (Component, DeferredComponent)):
                    raise TypeError(
                        f"invalid component given, expected type "
                        f"`Component` or `DeferredComponent` got {type(c)!r}"
                    )

                if isinstance(c, DeferredComponent):
                    c = c(app=app)

                data = c.data.copy()

                # If its got a url we wont get invoked on a click
                # so we can ignore setting a reference id.
                if data.url is None:
                    reference_id = str(uuid.uuid4())
                    data.custom_id = f"{data.custom_id}:{reference_id}"
                    await state.set(
                        reference_id,
                        {
                            "parent": parent_interaction,
                            **self._payload.component_context,
                        },
                    )

                component_block.append(data)
            action_row = ActionRow(components=component_block)
            action_rows.append(action_row)

        resp = self._payload.dict()
        del resp["components"]
        data = ResponseData(**resp, components=action_rows)
        return ResponsePayload(type=self._response_type or default_type, data=data)
