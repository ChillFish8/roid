from roid.callers import OptionalAsyncCallable
from roid.exceptions import RoidException
from roid.interactions import Interaction


class CheckError(RoidException):
    """The default exception for internal / pre-made checks."""


class CommandCheck(OptionalAsyncCallable):
    async def __call__(self, interaction: Interaction) -> Interaction:
        return await super().__call__(interaction)
