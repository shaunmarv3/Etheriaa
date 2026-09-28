"""Uploaded files on disk, encrypted (spec 5.2). Files live under a random
storage key, never under the user's filename."""

import os
import re
import tempfile
import uuid
from pathlib import Path

from etheria.core.crypto import decrypt_blob, encrypt_blob

_KEY = re.compile(r"[0-9a-f]{32}")


class FileStore:
    def __init__(self, root: Path, key: bytes) -> None:
        self._root = root
        self._key = key

    def path_for(self, storage_key: str) -> Path:
        if not _KEY.fullmatch(storage_key):
            raise ValueError("invalid storage key")
        return self._root / storage_key[:2] / storage_key

    def save(self, data: bytes) -> str:
        storage_key = uuid.uuid4().hex
        path = self.path_for(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = encrypt_blob(self._key, data, storage_key.encode())
        # Write then rename: a crash never leaves a half-written file under the real name.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(blob)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return storage_key

    def read(self, storage_key: str) -> bytes:
        blob = self.path_for(storage_key).read_bytes()
        return decrypt_blob(self._key, blob, storage_key.encode())

    def delete(self, storage_key: str) -> None:
        self.path_for(storage_key).unlink(missing_ok=True)
