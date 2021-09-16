class RoidException(Exception):
    """ The catch all for any roid exceptions which should be catchable. """


class HTTPException(RoidException):
    """ A exception raised by doing a REST call. """

    def __init__(self, status: int = 400, body: str = ""):
        self.status = status
        self.body = body

    def __str__(self):
        return f"status={self.status}, message={self.body}"


class CommandRejected(HTTPException):
    """ Raised when an invalid command is set to be registed. """

    def __init__(self, status: int = 400, body: str = ""):
        self.status = status
        self.body = body

    def __str__(self):
        return f"status={self.status}, message={self.body}"


class InvalidCommandOptionType(RoidException):
    """ The given option has being hinted as being a invalid type. """
