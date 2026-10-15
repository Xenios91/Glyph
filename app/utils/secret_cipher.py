"""Symmetric encryption for secrets at rest.

Provides a thin wrapper around :class:`cryptography.fernet.Fernet` so that
per-user LLM API keys are stored encrypted in the database rather than in
plaintext. The cipher key comes from the ``secret_cipher_key`` setting
(env var ``GLYPH_SECRET_CIPHER_KEY``); see :mod:`app.config.settings`.

The key may be either a real Fernet key (a 32-byte URL-safe base64 string,
generate one with::

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

or any passphrase: when the value is not a valid Fernet key it is turned into
one deterministically via SHA-256, so operators can set an arbitrary secret.

Stored values are prefixed with a version tag (``enc1:``) so that future
re-encryption schemes can be detected and migrated without ambiguity. A value
without the prefix is treated as legacy plaintext (pre-encryption) and is
returned as-is; it is re-encrypted the next time the row is upserted.
"""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

#: Version prefix for encrypted API keys. Bump to ``enc2:`` for a future
#: re-encryption scheme and add a migration path that re-encrypts ``enc1:``
#: values.
ENC_PREFIX = "enc1:"


def _derive_fernet_key(key: str | bytes) -> bytes:
    """Return a valid Fernet key for the given input.

    If the input is already a valid Fernet key it is used as-is; otherwise it
    is treated as a passphrase and a Fernet key is derived deterministically
    via SHA-256 (URL-safe base64 of the digest).

    Args:
        key: A Fernet key or an arbitrary passphrase.

    Returns:
        A 32-byte URL-safe base64-encoded Fernet key.

    """
    raw = key.encode() if isinstance(key, str) else key
    try:
        Fernet(raw)  # validate
        return raw
    except Exception:
        digest = hashlib.sha256(raw).digest()
        return base64.urlsafe_b64encode(digest)


class SecretCipher:
    """Symmetric encryption for secrets at rest (Fernet)."""

    def __init__(self, key: str | bytes) -> None:
        """Initialize the cipher with a Fernet key or passphrase.

        Args:
            key: A 32-byte URL-safe base64-encoded Fernet key, or any
                passphrase (derived to a Fernet key via SHA-256).

        Raises:
            ValueError: If the key is empty.

        """
        if not key:
            raise ValueError("Secret cipher key must not be empty")
        self._fernet = Fernet(_derive_fernet_key(key))

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext secret and return a versioned token.

        Args:
            plaintext: The secret to encrypt (e.g. an API key).

        Returns:
            The ``enc1:``-prefixed base64url Fernet token.

        """
        token = self._fernet.encrypt(plaintext.encode())
        return f"{ENC_PREFIX}{token.decode()}"

    def decrypt(self, token: str) -> str:
        """Decrypt a versioned token back to the original secret.

        Args:
            token: A value as stored in the database. If it carries the
                ``enc1:`` prefix it is decrypted; otherwise it is returned
                unchanged (legacy plaintext fallback).

        Returns:
            The decrypted secret, or the input unchanged when it is legacy
            plaintext.

        Raises:
            InvalidToken: When the token is prefixed but cannot be decrypted
                (key rotation or corruption).

        """
        if not token.startswith(ENC_PREFIX):
            # Legacy plaintext stored before encryption was introduced.
            return token
        payload = token[len(ENC_PREFIX):]
        return self._fernet.decrypt(payload.encode()).decode()

    @staticmethod
    def is_encrypted(value: str) -> bool:
        """Return True when the value carries the encryption prefix."""
        return value.startswith(ENC_PREFIX)


def get_secret_cipher() -> SecretCipher:
    """Build a :class:`SecretCipher` from the application settings.

    Returns:
        A cipher instance backed by the configured ``secret_cipher_key``.

    Raises:
        ValueError: If the configured key is not a valid Fernet key.

    """
    from app.config.settings import get_settings

    return SecretCipher(get_settings().secret_cipher_key)


def decrypt_api_key(stored: str) -> str:
    """Decrypt a stored API key, tolerating legacy plaintext and bad tokens.

    This is the repository-boundary helper: it never raises. A legacy
    plaintext value is returned as-is; a token that fails to decrypt (e.g.
    after a key rotation) logs a warning and returns an empty string so the
    key is treated as unset rather than crashing the request.

    Args:
        stored: The raw value read from the database.

    Returns:
        The decrypted key, or "" when the value is empty or undecryptable.

    """
    if not stored:
        return ""
    try:
        return get_secret_cipher().decrypt(stored)
    except InvalidToken:
        logger.warning(
            "Stored LLM API key could not be decrypted (key rotation or corruption); "
            "treating it as unset"
        )
        return ""
