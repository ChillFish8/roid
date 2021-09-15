import aioredis
from typing import Optional


class StorageBackend:
    def __init__(self, **context):
        raise NotImplemented()

    async def store(self, key: str, value: bytes):
        """
        Stores a given key with it's serialized value.

        args:
            
        """

        raise NotImplemented()

    async def get(self, key: str) -> Optional[bytes]:
        """
        Gets a key's serialized value if it exists.

        returns:
            The bytes associated with the given key otherwise None is returned.
        """

        raise NotImplemented()

    async def clear(self):
        """
        Clears the state storage.
        """

        raise NotImplemented()



class RedisBackend(StorageBackend):
    def __init__(self):