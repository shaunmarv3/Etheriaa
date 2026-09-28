"""AES-256-GCM for files at rest (spec 5.2, DPDP Rule 6 row "encryption").

Blob format: nonce (12 random bytes) || ciphertext || tag (16 bytes). The
caller passes associated data (the storage key), so a blob copied to another
name fails authentication instead of decrypting as the wrong document."""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from etheria.core.settings import Settings

NONCE_BYTES = 12


def encryption_key(settings: Settings) -> bytes:
    return base64.b64decode(settings.data_encryption_key.get_secret_value())


def encrypt_blob(key: bytes, data: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(key).encrypt(nonce, data, aad)


def decrypt_blob(key: bytes, blob: bytes, aad: bytes) -> bytes:
    """Raises cryptography.exceptions.InvalidTag on a wrong key, wrong aad or tampering."""
    return AESGCM(key).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], aad)
