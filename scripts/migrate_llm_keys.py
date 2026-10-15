"""One-time migration: encrypt legacy plaintext LLM API keys at rest.

Iterates the ``llm_user_configs`` rows in the auth database and re-encrypts
any ``api_key`` stored as plaintext (i.e. without the ``enc1:`` prefix).
Idempotent: rows already carrying the prefix are skipped, so the script can be
re-run safely.

Run from the project root:

    python -m scripts.migrate_llm_keys

The encryption key is taken from the ``secret_cipher_key`` setting
(env var ``GLYPH_SECRET_CIPHER_KEY``). In production set that variable to a
real Fernet key before running so the re-encrypted values are not protected by
the development default.
"""

import os
import sqlite3

from app.utils.secret_cipher import ENC_PREFIX, get_secret_cipher
from loguru import logger


def _data_dir() -> str:
    """Return the data directory for the SQLite databases (mirrors the app)."""
    return os.environ.get("GLYPH_DATA_DIR", "data")


def main() -> None:
    """Re-encrypt any plaintext LLM API keys in the auth database."""
    cipher = get_secret_cipher()
    db_path = os.path.join(_data_dir(), "auth.db")
    if not os.path.exists(db_path):
        logger.warning("Auth database not found at {}; nothing to do", db_path)
        return

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT id, user_id, api_key FROM llm_user_configs").fetchall()
        updated = 0
        for row_id, user_id, api_key in rows:
            if not api_key or api_key.startswith(ENC_PREFIX):
                continue
            conn.execute(
                "UPDATE llm_user_configs SET api_key = ? WHERE id = ?",
                (cipher.encrypt(api_key), row_id),
            )
            updated += 1
            logger.info("Re-encrypted LLM API key for user {}", user_id)
        conn.commit()
        logger.info("LLM key migration complete: {} row(s) re-encrypted", updated)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
