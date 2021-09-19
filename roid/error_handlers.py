from roid.helpers import UserMissingPermissions
from roid.response import Response
from roid.exceptions import AbortInvoke
from roid.objects import ResponseFlags


def handle_missing_permissions(error: UserMissingPermissions) -> Response:
    return Response(content=error.message, flags=ResponseFlags.EPHEMERAL)


def handle_abort_invoke(error: AbortInvoke) -> Response:
    return Response(**error.details)


KNOWN_ERRORS = {
    UserMissingPermissions: handle_missing_permissions,
    AbortInvoke: handle_abort_invoke,
}
