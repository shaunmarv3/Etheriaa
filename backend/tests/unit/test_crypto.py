import pytest
from cryptography.exceptions import InvalidTag

from etheria.core.crypto import decrypt_blob, encrypt_blob
from etheria.ingestion.storage import FileStore

K = bytes(range(32))


def test_roundtrip() -> None:
    assert decrypt_blob(K, encrypt_blob(K, b"x", b"k1"), b"k1") == b"x"


def test_nonce_is_random() -> None:
    assert encrypt_blob(K, b"x", b"a") != encrypt_blob(K, b"x", b"a")


def test_wrong_aad_fails() -> None:
    with pytest.raises(InvalidTag):
        decrypt_blob(K, encrypt_blob(K, b"x", b"a"), b"b")


def test_tamper_fails() -> None:
    blob = bytearray(encrypt_blob(K, b"x", b"a"))
    blob[-1] ^= 1
    with pytest.raises(InvalidTag):
        decrypt_blob(K, bytes(blob), b"a")


def test_filestore_never_writes_plaintext(tmp_path) -> None:
    store = FileStore(tmp_path, K)
    key = store.save(b"%PDF-secret")
    (path,) = [p for p in tmp_path.rglob(key) if p.is_file()]
    assert b"secret" not in path.read_bytes()
    assert b"%PDF" not in path.read_bytes()
    assert store.read(key) == b"%PDF-secret"


def test_filestore_key_is_random_hex(tmp_path) -> None:
    store = FileStore(tmp_path, K)
    a, b = store.save(b"one"), store.save(b"one")
    assert a != b
    assert len(a) == 32 and int(a, 16) >= 0


def test_filestore_file_moved_to_other_key_does_not_decrypt(tmp_path) -> None:
    store = FileStore(tmp_path, K)
    a, b = store.save(b"alpha"), store.save(b"beta")
    store.path_for(b).write_bytes(store.path_for(a).read_bytes())
    with pytest.raises(InvalidTag):
        store.read(b)


def test_filestore_delete_is_idempotent(tmp_path) -> None:
    store = FileStore(tmp_path, K)
    key = store.save(b"x")
    store.delete(key)
    store.delete(key)
    with pytest.raises(FileNotFoundError):
        store.read(key)


def test_filestore_rejects_path_like_keys(tmp_path) -> None:
    store = FileStore(tmp_path, K)
    with pytest.raises(ValueError):
        store.read("../../etc/passwd")
