from roid.helpers import UserMissingPermissions
from roid.response import Response, ResponseFlags


def handle_missing_permissions(error: UserMissingPermissions) -> Response:
    return Response(content=error.message, flags=ResponseFlags.EPHEMERAL)


KNOWN_ERRORS = {UserMissingPermissions: handle_missing_permissions}
