import asyncio
import aioredis
import threading
import queue
import sqlite3

from typing import Optional


class StorageBackend:
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

    async def startup(self):
        """
        A applicable startup task that gets called just before the server
        starts accepting connections.

        The backend should do any needed startup procedures in this task e.g. connect.
        """

        ...

    async def shutdown(self):
        """
        A applicable shutdown task that gets called just before the server closes.

        The backend should do any needed shutdown procedures in this task.
        """

        ...


class RedisBackend(StorageBackend):
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        **extra,
    ):
        self._redis = aioredis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            **extra,
        )

    async def store(self, key: str, value: bytes):
        await self._redis.set(key, value)

    async def get(self, key: str) -> Optional[bytes]:  # noqa
        await self._redis.get(key)

    async def shutdown(self):
        await self._redis.close()


class SqliteBackend(StorageBackend):
    def __init__(self, db_name: str = "managed-state"):
        self._runner = _SqliteRunner(db_name)

    async def shutdown(self):
        self._runner.shutdown()  # noqa

    async def store(self, key: str, value: bytes):
        op = _SqliteOp("SET", {"key": key, "value": value})
        self._runner.submit(op)
        return await op.wait()

    async def get(self, key: str) -> Optional[bytes]:  # noqa
        op = _SqliteOp("GET", {"key": key})
        self._runner.submit(op)
        return await op.wait()


class _SqliteOp:
    def __init__(self, action: str, data: dict):
        self.action = action
        self.data = data

        self._loop = asyncio.get_running_loop()
        self._resolve = self._loop.create_future()

    def set_result(self, *args):
        self._loop.call_soon_threadsafe(self._resolve.set_result, *args)

    async def wait(self):
        return await self._resolve


class _SqliteRunner:
    def __init__(self, db_name: str):
        self._queue = queue.Queue()
        self._running = True

        self._thread = threading.Thread(target=self._runner, args=(db_name,))
        self._thread.start()

    def submit(self, op: _SqliteOp):
        self._queue.put_nowait(op)

    def shutdown(self):
        self._running = False
        self._thread.join()

    def _runner(self, db_name: str):
        db = sqlite3.connect(f"file:{db_name}?mode=memory&cache=shared")

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS store (
                key TEXT PRIMARY KEY,
                store_value BLOB
            )           
        """
        )

        while self._running:
            event: _SqliteOp = self._queue.get()

            if event.action == "SET":
                self._set(db, **event.data)
                event.set_result(None)
            elif event.action == "GET":
                result = self._get(db, **event.data)
                event.set_result(result)
            else:
                raise Exception(f"Unknown action {event.action!r}")

    @staticmethod
    def _set(db: sqlite3.Connection, key: str, value: Optional[bytes]):
        cur = db.cursor()
        cur.execute("INSERT INTO store (key, store_value) VALUES (?, ?)", (key, value))
        cur.close()

    @staticmethod
    def _get(db: sqlite3.Connection, key: str) -> Optional[bytes]:
        cur = db.cursor()
        cur.execute(
            "SELECT (key, store_value) FROM store WHERE key = ? LIMIT 1", (key,)
        )
        v = cur.fetchone()
        cur.close()
        return v
