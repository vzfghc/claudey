"""At-rest secret encryption envelope (``enc:v1:`` AES-256-GCM).

Secrets persisted by Claudey (currently custom-provider API keys) are stored
either as legacy plaintext or behind the ``enc:v1:`` envelope. The envelope
ports OmniRoute's format so existing tooling recognizes it:

* Wire form: ``enc:v1:<urlsafe-base64(iv || ciphertext || auth_tag)>``
* AES-256-GCM with a random 16-byte IV and a pinned 16-byte GCM auth tag.
* The 32-byte key is derived from the configured passphrase via scrypt with a
  static (pinned) 16-byte salt, so the passphrase itself is never persisted.

Encryption is **opt-in**: no key means plaintext fallback (back-compat), and a
configured key transparently upgrades plaintext on the next write.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENCRYPTED_PREFIX = "enc:v1:"

_KEY_LEN = 32
_IV_LEN = 16
_TAG_LEN = 16
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024
# Pinned static salt (16 bytes) matching the OmniRoute `enc:v1:` envelope.
_SCRYPT_SALT = b"claudey-at-rest-v1"


class SecretCryptoError(ValueError):
    """Raised when an at-rest secret cannot be encrypted or decrypted."""


def is_encrypted(value: str) -> bool:
    """Return whether a stored value uses the ``enc:v1:`` envelope."""
    return value.startswith(ENCRYPTED_PREFIX)


def derive_key(material: str) -> bytes:
    """Derive the 32-byte AES-256 key from a passphrase via scrypt."""
    if not material:
        raise SecretCryptoError(
            "No encryption key configured; cannot derive an at-rest key."
        )
    return hashlib.scrypt(
        material.encode("utf-8"),
        salt=_SCRYPT_SALT,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
        dklen=_KEY_LEN,
    )


def encrypt_secret(plaintext: str, key_material: str) -> str:
    """Encrypt ``plaintext`` into an ``enc:v1:`` envelope string."""
    key = derive_key(key_material)
    iv = secrets.token_bytes(_IV_LEN)
    sealed = AESGCM(key).encrypt(iv, plaintext.encode("utf-8"), None)
    body = base64.urlsafe_b64encode(iv + sealed).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{body}"


def decrypt_secret(token: str, key_material: str) -> str:
    """Decrypt an ``enc:v1:`` envelope string, authenticating the GCM tag.

    Passing a plaintext value returns it unchanged (legacy back-compat).
    """
    if not is_encrypted(token):
        return token
    key = derive_key(key_material)
    try:
        raw = base64.urlsafe_b64decode(token[len(ENCRYPTED_PREFIX) :] + "==")
    except ValueError, binascii.Error:
        raise SecretCryptoError("Stored secret is not valid base64.") from None
    if len(raw) < _IV_LEN + _TAG_LEN:
        raise SecretCryptoError("Stored secret envelope is truncated.")
    iv, sealed = raw[:_IV_LEN], raw[_IV_LEN:]
    try:
        plaintext = AESGCM(key).decrypt(iv, sealed, None)
    except Exception as error:
        raise SecretCryptoError(
            "Stored secret failed authentication (wrong key or corrupt data)."
        ) from error
    return plaintext.decode("utf-8")


def generate_key_material() -> str:
    """Return a fresh 32-byte passphrase (hex) suitable for the env var."""
    return os.urandom(32).hex()
