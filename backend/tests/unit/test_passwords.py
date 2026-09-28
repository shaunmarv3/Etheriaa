from etheria.auth.passwords import dummy_hash, hash_password, needs_rehash, verify_password

PW = "correct horse battery"


def test_hash_is_argon2id_and_salted() -> None:
    first, second = hash_password(PW), hash_password(PW)
    assert first.startswith("$argon2id$")
    assert first != second


def test_verify_accepts_the_right_password_only() -> None:
    stored = hash_password(PW)
    assert verify_password(stored, PW) is True
    assert verify_password(stored, PW + "!") is False


def test_verify_never_raises_on_a_malformed_hash() -> None:
    assert verify_password("not-a-hash", PW) is False


def test_fresh_hashes_do_not_need_rehash() -> None:
    assert needs_rehash(hash_password(PW)) is False


def test_dummy_hash_is_a_cached_argon2id_hash() -> None:
    assert dummy_hash() is dummy_hash()
    assert dummy_hash().startswith("$argon2id$")
