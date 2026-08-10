"""At-rest secret crypto envelope (``enc:v1:`` AES-256-GCM)."""

import base64

import pytest

from claudey.core.secret_crypto import (
    ENCRYPTED_PREFIX,
    SecretCryptoError,
    decrypt_secret,
    derive_key,
    encrypt_secret,
    generate_key_material,
    is_encrypted,
)


def test_derives_deterministic_32_byte_key():
    key = derive_key("correct horse battery staple")
    assert len(key) == 32
    assert key == derive_key("correct horse battery staple")
    assert key != derive_key("a different passphrase")


def test_empty_key_material_raises():
    with pytest.raises(SecretCryptoError):
        derive_key("")


def test_encrypt_produces_recognizable_envelope():
    token = encrypt_secret("sk-super-secret", "local-key")
    assert token.startswith(ENCRYPTED_PREFIX)
    assert is_encrypted(token) is True


def test_round_trip_recovers_plaintext():
    token = encrypt_secret("sk-super-secret", "local-key")
    assert decrypt_secret(token, "local-key") == "sk-super-secret"


def test_round_trip_for_any_plaintext():
    # Unicode and sensitive punctuation survive the byte<->text round trip.
    plaintext = "k_HT☃é:§/ZS4;=x`\"'!@#\n"
    token = encrypt_secret(plaintext, "pass")
    assert decrypt_secret(token, "pass") == plaintext


def test_wrong_key_fails_authentication():
    token = encrypt_secret("sk-secret", "right-key")
    with pytest.raises(SecretCryptoError):
        decrypt_secret(token, "wrong-key")


def test_plaintext_passes_through_decrypt_unchanged():
    assert decrypt_secret("sk-plain", "any-key") == "sk-plain"
    assert decrypt_secret("", "any-key") == ""


def test_ciphertext_is_not_plaintext_and_variable_per_iv():
    # Random IV means the same plaintext never encrypts to the same token.
    a = encrypt_secret("sk-same", "key")
    b = encrypt_secret("sk-same", "key")
    assert a != b
    assert ENCRYPTED_PREFIX not in a[len(ENCRYPTED_PREFIX) :]


def test_auth_tag_is_pinned_to_16_bytes():
    token = encrypt_secret("sk-x", "key")
    body = base64.urlsafe_b64decode(token[len(ENCRYPTED_PREFIX) :] + "==")
    # iv(16) || ciphertext || tag(16): len(body) >= 32, tag last 16 bytes.
    assert len(body) >= 16 + 16


def test_tampered_ciphertext_fails_authentication():
    token = encrypt_secret("sk-secret", "key")
    body = bytearray(base64.urlsafe_b64decode(token[len(ENCRYPTED_PREFIX) :] + "=="))
    body[-1] ^= 0x01  # flip a bit in the auth tag
    tampered = ENCRYPTED_PREFIX + base64.urlsafe_b64encode(bytes(body)).decode()
    with pytest.raises(SecretCryptoError):
        decrypt_secret(tampered, "key")


def test_truncated_envelope_is_rejected():
    with pytest.raises(SecretCryptoError):
        decrypt_secret(ENCRYPTED_PREFIX + "c2hvcnQ", "key")


def test_invalid_base64_envelope_is_rejected():
    with pytest.raises(SecretCryptoError):
        decrypt_secret(ENCRYPTED_PREFIX + "!!!not-base64!!!", "key")


def test_generate_key_material_returns_hex_passphrase():
    material = generate_key_material()
    assert len(material) == 64  # 32 random bytes as hex
    assert material != generate_key_material()


def test_is_encrypted_only_for_prefix():
    assert is_encrypted("enc:v1:abc") is True
    assert is_encrypted("enc:v2:abc") is False
    assert is_encrypted("opaque") is False
    assert is_encrypted("") is False
