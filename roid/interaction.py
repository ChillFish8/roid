from enum import IntEnum, auto


class InteractionType(IntEnum):
    PING = auto()
    APPLICATION_COMMAND = auto()
    MESSAGE_COMPONENT = auto()
