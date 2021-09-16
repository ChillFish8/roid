import asyncio
import pickle

from typing import Any

from roid.state.storage import StorageBackend


class ManagedState:
    """ A helper for cross-process shared state. """

    def __init__(self, backend: StorageBackend):
        self._loop = asyncio.get_running_loop()
        self._backend = backend

    async def set(self, key: str, value: Any):
        """
        Sets a key to a given value.

        args:
            key:
                The unique key for the value.

            value:
                The value for the given key, this must be serializable by pickle.
        """

        data = pickle.dumps(value)
        await self._backend.store(key, data)

    async def get(self, key: str) -> Any:
        """
        Gets a value for a given key.

        args:
            key:
                The unique key for the value.

        returns:
            The value associated with this key or None.
        """

        data = await self._backend.get(key)
        if data is None:
            return None

        return pickle.loads(data)

    def set_sync(self, key: str, value: Any):
        """
        Sets a key to a given value.

        args:
            key:
                The unique key for the value.

            value:
                The value for the given key, this must be serializable by pickle.
        """

        fut = asyncio.run_coroutine_threadsafe(self.set(key, value), self._loop)
        return fut.result()

    def get_sync(self, key: str):
        """
        Gets a value for a given key.

        args:
            key:
                The unique key for the value.

        returns:
            The value associated with this key or None.
        """

        fut = asyncio.run_coroutine_threadsafe(self.get(key), self._loop)
        return fut.result()
