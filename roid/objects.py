from datetime import datetime
from enum import IntEnum, auto, Enum
from functools import reduce
from operator import or_
from typing import Optional, List, Union

from pydantic import BaseModel, constr, validate_arguments, AnyHttpUrl, validator

from roid.http import DISCORD_CDN_DOMAIN


class PremiumType(IntEnum):
    NONE = auto()
    NITRO_CLASSIC = auto()
    NITRO = auto()


class UserFlags(IntEnum):
    NONE = 0
    DISCORD_EMPLOYEE = 1 << 0
    PARTNERED_SERVER_OWNER = 1 << 1
    HYPE_SQUAD_EVENTS = 1 << 2
    BUG_HUNTER_LVL_1 = 1 << 3
    HOUSE_BRAVERY = 1 << 6
    HOUSE_BRILLIANCE = 1 << 7
    HOUSE_BALANCE = 1 << 8
    EARLY_SUPPORTER = 1 << 9
    TEAM_USER = 1 << 10
    BUG_HUNTER_LVL_2 = 1 << 14
    VERIFIED_BOT = 1 << 16
    EARLY_VERIFIED_BOT_DEVELOPER = 1 << 17
    DISCORD_CERTIFIED_MODERATOR = 1 << 18


class User(BaseModel):
    id: int
    username: str
    discriminator: int
    avatar: Optional[str] = None
    bot: bool = False
    system: bool = False
    banner: Optional[str] = None
    accent_color: Optional[int] = None
    public_flags: int = 0

    @property
    def avatar_url(self) -> str:
        fmt = "png"
        if self.avatar is None:
            return f"https://{DISCORD_CDN_DOMAIN}/embed/avatars/{self.discriminator % 5}.png"

        if self.avatar.startswith("a_"):
            fmt = "gif"

        return f"https://{DISCORD_CDN_DOMAIN}/avatars/{self.id}/{self.avatar}.{fmt}"

    def avatar_url_as(self, *, fmt="png"):
        if self.avatar is None:
            return f"https://{DISCORD_CDN_DOMAIN}/embed/avatars/{self.discriminator % 5}.{fmt}"

        return f"https://{DISCORD_CDN_DOMAIN}/avatars/{self.id}/{self.avatar}.{fmt}"


class CompletedOption(BaseModel):
    name: str
    value: str


class RoleTags(BaseModel):
    bot_id: int = None
    integration_id: int = None


class Role(BaseModel):
    id: int
    name: str
    color: int
    hoist: bool
    position: int
    permissions: int
    managed: bool
    mentionable: bool
    tags: Optional[RoleTags]


class MemberPermissions(IntEnum):
    CREATE_INSTANT_INVITE = 1 << 0
    KICK_MEMBERS = 1 << 1
    BAN_MEMBERS = 1 << 2
    ADMINISTRATOR = 1 << 3
    MANAGE_CHANNELS = 1 << 4
    MANAGE_GUILD = 1 << 5
    ADD_REACTIONS = 1 << 6
    VIEW_AUDIT_LOG = 1 << 7
    PRIORITY_SPEAKER = 1 << 8
    STREAM = 1 << 9
    VIEW_CHANNEL = 1 << 10
    SEND_MESSAGES = 1 << 11
    SEND_TTS_MESSAGE = 1 << 12
    MANAGE_MESSAGE = 1 << 13
    EMBED_LINKS = 1 << 14
    ATTACH_FILES = 1 << 15
    READ_MESSAGE_HISTORY = 1 << 16
    MENTION_EVERYONE = 1 << 17
    USE_EXTERNAL_EMOJIS = 1 << 18
    VIEW_GUILD_INSIGHTS = 1 << 19
    CONNECT = 1 << 20
    SPEAK = 1 << 21
    MUTE_MEMBERS = 1 << 22
    DEAFEN_MEMBERS = 1 << 23
    MOVE_MEMBERS = 1 << 24
    USE_VAD = 1 << 25
    CHANGE_NICKNAME = 1 << 26
    MANAGE_NICKNAMES = 1 << 27
    MANAGE_ROLES = 1 << 28
    MANAGE_WEBHOOKS = 1 << 29
    MANAGE_EMOJIS_AND_STICKERS = 1 << 30
    USE_APPLICATION_COMMANDS = 1 << 31
    REQUEST_TO_SPEAK = 1 << 32
    MANAGE_THREADS = 1 << 34
    USE_PUBLIC_THREADS = 1 << 35
    USE_PRIVATE_THREADS = 1 << 36
    USE_EXTERNAL_STICKERS = 1 << 37


class Member(BaseModel):
    user: User = None
    nick: Optional[str] = None
    roles: List[int]
    joined_at: datetime
    premium_since: Optional[datetime] = None
    deaf: bool = False
    mute: bool = False
    pending: bool = False
    permissions: int = 0

    def has_permissions(self, flags: Union[int, List[MemberPermissions]]) -> bool:
        if isinstance(flags, list):
            flags = reduce(or_, map(lambda x: x.value, flags))
        return self.permissions & flags != 0


class ChannelType(IntEnum):
    GUILD_TEXT = 0
    DM = 1
    GUILD_VOICE = 2
    GROUP_DM = 3
    GUILD_CATEGORY = 4
    GUILD_NEWS = 5
    GUILD_STORE = 6
    GUILD_NEWS_THREAD = 10
    GUILD_PUBLIC_THREAD = 11
    GUILD_PRIVATE_THREAD = 12
    GUILD_STAGE_VOICE = 13


class OverwriteType(IntEnum):
    ROLE = 0
    MEMBER = 1


class PermissionOverwrite(BaseModel):
    id: int
    type: OverwriteType
    allow: int
    deny: int


class ThreadMetaData(BaseModel):
    archived: bool
    auto_archive_duration: int
    archive_timestamp: datetime
    locked: bool
    invitable: bool = False


class ThreadMember(BaseModel):
    id: int
    user_id: Optional[int]
    join_timestamp: datetime
    flags: int


class Channel(BaseModel):
    id: int
    type: ChannelType
    name: Optional[str] = None
    parent_id: Optional[int]
    thread_metadata: Optional[ThreadMetaData]
    permissions: Optional[int]

    @property
    def is_dm(self) -> bool:
        return self.type == ChannelType.DM

    @property
    def is_category(self) -> bool:
        return self.type == ChannelType.GUILD_CATEGORY

    @property
    def is_thread(self) -> bool:
        return self.type in (
            ChannelType.GUILD_NEWS_THREAD,
            ChannelType.GUILD_PUBLIC_THREAD,
            ChannelType.GUILD_PRIVATE_THREAD,
        )


class ChannelMention(BaseModel):
    id: int
    guild_id: int
    type: ChannelType
    name: str


class Attachment(BaseModel):
    id: int
    filename: str
    content_type: Optional[str]
    size: int
    url: AnyHttpUrl
    proxy_url: AnyHttpUrl
    height: Optional[int]
    width: Optional[int]


class EmbedType(Enum):
    RICH = "rich"
    IMAGE = "image"
    VIDEO = "video"
    GIFV = "gifv"
    ARTICLE = "article"
    LINK = "link"


class EmbedFooter(BaseModel):
    text: constr(min_length=1, max_length=2048, strip_whitespace=True)
    icon_url: Optional[AnyHttpUrl]
    proxy_icon_url: Optional[AnyHttpUrl]


class EmbedImage(BaseModel):
    url: AnyHttpUrl
    proxy_url: Optional[AnyHttpUrl]
    height: Optional[int]
    width: Optional[int]


class EmbedVideo(BaseModel):
    url: Optional[AnyHttpUrl]
    proxy_url: Optional[AnyHttpUrl]
    height: Optional[int]
    width: Optional[int]


class EmbedProvider(BaseModel):
    name: Optional[str]
    url: Optional[AnyHttpUrl]


class EmbedAuthor(BaseModel):
    name: constr(min_length=1, max_length=256, strip_whitespace=True)
    url: Optional[AnyHttpUrl]
    icon_url: Optional[AnyHttpUrl]
    proxy_icon_url: Optional[AnyHttpUrl]


class EmbedField(BaseModel):
    name: constr(min_length=1, max_length=256, strip_whitespace=True)
    value: constr(min_length=1, max_length=1024, strip_whitespace=True)
    inline: bool = False


class Embed(BaseModel):
    title: Optional[constr(min_length=1, max_length=256, strip_whitespace=True)]
    type: Optional[EmbedType]
    description: Optional[constr(min_length=1, max_length=4096, strip_whitespace=True)]
    url: Optional[AnyHttpUrl]
    timestamp: Optional[datetime]
    color: Optional[int]
    footer: Optional[EmbedFooter]
    image: Optional[EmbedImage]
    thumbnail: Optional[EmbedImage]
    video: Optional[EmbedVideo]
    provider: Optional[EmbedProvider]
    author: Optional[EmbedAuthor]
    fields: Optional[List[EmbedField]]

    @validate_arguments
    def set_image(self, *, url: str):
        self.image = EmbedImage(url=url)

    @validate_arguments
    def set_thumbnail(self, *, url: str):
        self.thumbnail = EmbedImage(url=url)

    @validate_arguments
    def set_footer(
        self,
        text: constr(min_length=1, max_length=2048, strip_whitespace=True),
        *,
        icon_url: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.footer = EmbedFooter(text=text, icon_url=icon_url)
        self.timestamp = timestamp

    @validate_arguments
    def set_author(
        self,
        name: constr(min_length=1, max_length=256, strip_whitespace=True),
        *,
        url: Optional[str] = None,
        icon_url: Optional[str] = None,
    ):
        self.author = EmbedAuthor(name=name, url=url, icon_url=icon_url)

    @validate_arguments
    def add_field(
        self,
        *,
        name: constr(min_length=1, max_length=256, strip_whitespace=True),
        value: constr(min_length=1, max_length=1024, strip_whitespace=True),
        inline: bool = False,
    ):
        if self.fields is None:
            self.fields = []

        self.fields.append(EmbedField(name=name, value=value, inline=inline))


class PartialEmoji(BaseModel):
    id: Optional[int]
    name: Optional[str]
    roles: Optional[List[int]]
    user: Optional[User]
    require_colon: bool = False
    managed: bool = False
    animated: bool = False
    available: bool = False


class Reaction(BaseModel):
    count: int
    me: bool
    emoji: PartialEmoji


class MessageType(IntEnum):
    DEFAULT = 0
    RECIPIENT_ADD = 1
    RECIPIENT_REMOVE = 2
    CALL = 3
    CHANNEL_NAME_CHANGE = 4
    CHANNEL_ICON_CHANGE = 5
    CHANNEL_PINNED_MESSAGE = 6
    GUILD_MEMBER_JOIN = 7
    USER_PREMIUM_GUILD_SUBSCRIPTION = 8
    USER_PREMIUM_GUILD_SUBSCRIPTION_TIER_1 = 9
    USER_PREMIUM_GUILD_SUBSCRIPTION_TIER_2 = 10
    USER_PREMIUM_GUILD_SUBSCRIPTION_TIER_3 = 11
    CHANNEL_FOLLOW_ADD = 12
    GUILD_DISCOVERY_DISQUALIFIED = 14
    GUILD_DISCOVERY_REQUALIFIED = 15
    GUILD_DISCOVERY_GRACE_PERIOD_INITIAL_WARNING = 16
    GUILD_DISCOVERY_GRACE_PERIOD_FINAL_WARNING = 17
    THREAD_CREATED = 18
    REPLY = 19
    CHAT_INPUT_COMMAND = 20
    THREAD_STARTER_MESSAGE = 21
    GUILD_INVITE_REMINDER = 22
    CONTEXT_MENU_COMMAND = 23


class MessageActivityType(IntEnum):
    JOIN = 1
    SPECTATE = 2
    LISTEN = 3
    JOIN_REQUEST = 5


class MessageActivity(BaseModel):
    type: MessageActivityType
    part_id: Optional[str]


class MessageFlags(IntEnum):
    CROSS_POSTED = 1 << 0
    IS_CROSS_POST = 1 << 1
    SUPPRESS_EMBEDS = 1 << 2
    SOURCE_MESSAGE_DELETED = 1 << 3
    URGENT = 1 << 4
    HAS_THREAD = 1 << 5
    EPHEMERAL = 1 << 6
    LOADING = 1 << 7


class StickerFormatType(IntEnum):
    PING = auto()
    APNG = auto()
    LOTTIE = auto()


class StickerType(IntEnum):
    STANDARD = auto()
    GUILD = auto()


class StickerItem(BaseModel):
    id: int
    name: str
    format_type: StickerFormatType


class Sticker(BaseModel):
    id: int
    pack_id: Optional[int]
    name: str
    description: Optional[str]
    tags: str
    type: StickerType
    format_type: StickerFormatType
    available: bool = False
    guild_id: Optional[int]
    user: Optional[User]
    sort_value: Optional[int]


class PartialMessage(BaseModel):
    id: int
    channel_id: int
    guild_id: Optional[int]
    author: User
    member: Optional[Member]
    content: str
    timestamp: datetime
    edited_timestamp: Optional[datetime]
    tts: bool
    mention_everyone: bool
    mentions: List[User] = []
    mention_roles: List[int] = []
    mention_channels: Optional[List[ChannelMention]] = None
    attachments: List[Attachment]
    embeds: List[Embed]
    reactions: Optional[List[Reaction]]
    nonce: Optional[Union[int, str]]
    pinned: bool
    webhook_id: Optional[int]
    type: MessageType
    activity: Optional[MessageActivity]
    application_id: Optional[int]
    flags: Optional[int]
    thread: Optional[Channel]
    sticker_items: Optional[List[StickerItem]]
    stickers: Optional[List[Sticker]]


class AllowedMentionType(Enum):
    ROLES = "roles"
    USERS = "users"
    EVERYONE = "everyone"


class AllowedMentions(BaseModel):
    parse: List[AllowedMentionType] = []
    roles: List[str] = []
    users: List[str] = []

    @validator("roles", "users")
    def convert_snowflake(cls, v):
        try:
            return [int(i) for i in v]
        except ValueError:
            raise ValueError("field contains non-integer values")


class ResponseType(IntEnum):
    PONG = 1
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8


class ResponseFlags(IntEnum):
    EPHEMERAL = 1 << 6
