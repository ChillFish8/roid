from roid.helpers import UserMissingPermissions
from roid.response import ResponsePayload, response, ResponseFlags


def handle_missing_permissions(error: UserMissingPermissions) -> ResponsePayload:
    return response(content=error.message, flags=ResponseFlags.EPHEMERAL)


KNOWN_ERRORS = {UserMissingPermissions: handle_missing_permissions}
