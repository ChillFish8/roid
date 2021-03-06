import asyncio
import pickle
from datetime import timedelta

from typing import Any, Dict, Coroutine, Optional, Union

from roid.state.storage import StorageBackend


class State:
    """A general interface for a given storage backend."""

    def __init__(self, backend: StorageBackend):
        self._loop = asyncio.get_running_loop()
        self._backend = backend

    async def set(
        self, key: str, value: Any, ttl: Optional[Union[timedelta, float]] = None
    ):
        """
        Sets a key to a given value.

        Args:
            key:
                The unique key for the value.

            value:
                The value for the given key, this must be serializable by pickle.

            ttl:
                The time-to-live for the given value. If set to None this will never
                be deleted automatically.
        """

        if ttl is not None and isinstance(ttl, float):
            ttl = timedelta(seconds=ttl)

        data = pickle.dumps(value)
        await self._backend.store(key, data, ttl)

    async def get(self, key: str) -> Any:
        """
        Gets a value for a given key.

        Args:
            key:
                The unique key for the value.

        Returns:
            The value associated with this key or None.
        """

        data = await self._backend.get(key)
        if data is None:
            return None

        return pickle.loads(data)

    async def remove(self, key: str):
        """
        Removes the value for the given key from the collection if it exists.

        Args:
            key:
                The unique key to remove.
        """

        return await self._backend.remove(key)

    def set_sync(
        self, key: str, value: Any, ttl: Optional[Union[timedelta, float]] = None
    ):
        """
        Sets a key to a given value.

        Args:
            key:
                The unique key for the value.

            value:
                The value for the given key, this must be serializable by pickle.

            ttl:
                The time-to-live for the given value. If set to None this will never
                be deleted automatically.
        """

        if ttl is not None and isinstance(ttl, float):
            ttl = timedelta(seconds=ttl)

        fut = asyncio.run_coroutine_threadsafe(self.set(key, value, ttl), self._loop)
        return fut.result()

    def get_sync(self, key: str) -> Any:
        """
        Gets a value for a given key.

        Args:
            key:
                The unique key for the value.

        Returns:
            The value associated with this key or None.
        """

        fut = asyncio.run_coroutine_threadsafe(self.get(key), self._loop)
        return fut.result()

    def remove_sync(self, key: str):
        """
        Remove a key from the state.

        Args:
            key:
                The unique key to remove.
        """

        fut = asyncio.run_coroutine_threadsafe(self.remove(key), self._loop)
        return fut.result()


class ManagedState(State):
    """A state object that implements the startup and shutdown events."""

    async def startup(self):
        """Runs any setup stages on the storage backend."""
        await self._backend.startup()

    async def shutdown(self):
        """Runs any shutdown / cleanup stages on the storage backend."""
        await self._backend.shutdown()


class PrefixedState(State):
    """A state interface that adds a given prefix to every passed key."""

    def __init__(self, prefix: str, backend: StorageBackend):
        self.prefix = prefix

        super().__init__(backend)

    def set(self, key: str, value: Any, ttl: Optional[Union[timedelta, float]] = None):
        return super().set(f"{self.prefix}:{key}", value, ttl)

    def get(self, key: str) -> Coroutine[Any, Any, Any]:
        return super().get(f"{self.prefix}:{key}")

    def remove(self, key: str):
        return super().remove(f"{self.prefix}:{key}")

    def set_sync(
        self, key: str, value: Any, ttl: Optional[Union[timedelta, float]] = None
    ):
        return super().set_sync(f"{self.prefix}:{key}", value, ttl)

    def get_sync(self, key: str):
        return super().get_sync(f"{self.prefix}:{key}")

    def remove_sync(self, key: str):
        return super().remove_sync(f"{self.prefix}:{key}")


class MultiManagedState:
    """
    A alternative managed state that implements __getitem__ which
    allows for grouping of state on the same backend.

    This can potentially save various connections to things like Redis for example.
    """

    def __init__(self, backend: StorageBackend):
        """
        A alternative managed state that implements __getitem__ which
        allows for grouping of state on the same backend.

        This can potentially save various connections to things like Redis for example.

        Args:
            backend:
                The given storage backend to use.
        """

        self._loop = asyncio.get_running_loop()
        self._backend = backend
        self._prefixed_states: Dict[str, PrefixedState] = {}

    async def startup(self):
        """Runs any setup stages on the storage backend."""
        await self._backend.startup()

    async def shutdown(self):
        """Runs any shutdown / cleanup stages on the storage backend."""
        await self._backend.shutdown()

    def __getitem__(self, item: str):
        if item in self._prefixed_states:
            return self._prefixed_states[item]

        state = PrefixedState(item, self._backend)
        self._prefixed_states[item] = state

        return state

    def __delitem__(self, key: str):
        self._prefixed_states.pop(key, None)
