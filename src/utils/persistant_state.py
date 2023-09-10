import io
import os
import pickle
from typing import TypeVar, Generic

import aiofiles

T = TypeVar("T")


class PersistentState(Generic[T]):
    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = path
        self.initialized: bool = False

    def file_name(self) -> str:
        return os.path.join(self.path, f"state_{self.name}.pckl")

    async def initialize(self, obj: T):
        if not os.path.exists(self.file_name()):
            # pickle to file_name
            async with aiofiles.open(self.file_name(), "wb") as f:
                await f.write(pickle.dumps(obj))
        self.initialized = True

    async def get(self) -> T:
        if not self.initialized:
            raise Exception("You must call `initialize` before using `PersistantState`")

        async with aiofiles.open(self.file_name(), "rb") as f:
            pickled_bytes = await f.read()

            with io.BytesIO() as f:
                f.write(pickled_bytes)
                f.seek(0)
                return pickle.load(f)

    async def set(self, obj: T):
        if not self.initialized:
            raise Exception("You must call `initialize` before using `PersistantState`")

        async with aiofiles.open(self.file_name(), "wb") as f:
            await f.write(pickle.dumps(obj))
