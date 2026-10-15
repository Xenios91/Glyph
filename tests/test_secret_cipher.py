"""Unit tests for app.utils.secret_cipher (Fernet encryption of secrets at rest)."""

import pytest
from app.utils.secret_cipher import ENC_PREFIX, SecretCipher, decrypt_api_key
from cryptography.fernet import Fernet, InvalidToken


@pytest.fixture
def key() -> str:
    """A valid Fernet key for the tests."""
    return Fernet.generate_key().decode()


@pytest.fixture
def cipher(key: str) -> SecretCipher:
    return SecretCipher(key)


class TestSecretCipher:
    def test_round_trip(self, cipher: SecretCipher) -> None:
        token = cipher.encrypt("sk-abc-123")
        assert token.startswith(ENC_PREFIX)
        assert cipher.decrypt(token) == "sk-abc-123"

    def test_encrypt_produces_versioned_token(self, cipher: SecretCipher) -> None:
        token = cipher.encrypt("secret")
        assert token.startswith(ENC_PREFIX)
        assert cipher.is_encrypted(token)
        assert not cipher.is_encrypted("secret")

    def test_decrypt_legacy_plaintext_passthrough(self, cipher: SecretCipher) -> None:
        # A value without the prefix is returned unchanged (legacy plaintext).
        assert cipher.decrypt("legacy-plaintext") == "legacy-plaintext"

    def test_decrypt_wrong_key_raises_invalid_token(self, key: str) -> None:
        good = SecretCipher(key)
        bad = SecretCipher(Fernet.generate_key().decode())
        token = good.encrypt("top-secret")
        with pytest.raises(InvalidToken):
            bad.decrypt(token)

    def test_passphrase_is_derived_to_fernet_key(self) -> None:
        # An arbitrary (non-Fernet) passphrase is accepted and derived via SHA-256.
        c = SecretCipher("my-arbitrary-passphrase")
        token = c.encrypt("secret")
        assert c.decrypt(token) == "secret"

    def test_empty_key_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            SecretCipher("")


class TestDecryptApiKey:
    def test_empty_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert decrypt_api_key("") == ""

    def test_legacy_plaintext_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert decrypt_api_key("plain-key") == "plain-key"

    def test_encrypted_round_trip(self, monkeypatch: pytest.MonkeyPatch, key: str) -> None:
        monkeypatch.setattr("app.config.settings.get_settings", lambda: _FakeSettings(key))
        c = SecretCipher(key)
        token = c.encrypt("sk-xyz")
        assert decrypt_api_key(token) == "sk-xyz"

    def test_bad_token_returns_empty(self, monkeypatch: pytest.MonkeyPatch, key: str) -> None:
        monkeypatch.setattr("app.config.settings.get_settings", lambda: _FakeSettings(key))
        other = Fernet(Fernet.generate_key()).encrypt(b"rotated")
        assert decrypt_api_key(f"{ENC_PREFIX}{other.decode()}") == ""


class _FakeSettings:
    def __init__(self, key: str) -> None:
        self.secret_cipher_key = key
