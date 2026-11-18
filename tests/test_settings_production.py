"""Unit tests for the production security guards in ``app.config.settings``.

``_validate_production_settings`` refuses to start the app with unsafe
security-critical settings when ``GLYPH_ENV=production``. These tests cover
each guard branch (default/short JWT secret, default cipher key, empty
secret reset) plus the ``get_settings``/``reload_settings`` singleton
behavior.
"""

from typing import Any

import pytest
from app.config import settings as settings_module
from app.config.settings import GlyphSettings, _validate_production_settings
from loguru import logger

_STRONG_JWT = "a-very-strong-jwt-secret-that-is-long-enough-0123456789"
_STRONG_CIPHER = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


def _make_settings(**kwargs: Any) -> GlyphSettings:
    """Build a GlyphSettings instance with explicit security values."""
    kwargs.setdefault("jwt_secret_key", _STRONG_JWT)
    kwargs.setdefault("secret_cipher_key", _STRONG_CIPHER)
    kwargs.setdefault("use_https", True)
    return GlyphSettings(**kwargs)


class TestProductionJWTSecret:
    """JWT secret guard branches."""

    def test_prod_default_jwt_secret_raises(self, monkeypatch: Any) -> None:
        """The default placeholder JWT secret must be rejected in production."""
        monkeypatch.setenv("GLYPH_ENV", "production")
        settings = GlyphSettings()
        assert settings.jwt_secret_key == "change-me-in-production"
        with pytest.raises(RuntimeError, match="JWT secret key must be changed from default"):
            _validate_production_settings(settings)

    def test_prod_short_jwt_secret_raises(self, monkeypatch: Any) -> None:
        """A JWT secret shorter than 32 chars must be rejected in production."""
        monkeypatch.setenv("GLYPH_ENV", "production")
        settings = GlyphSettings(jwt_secret_key="short-secret")
        with pytest.raises(RuntimeError, match="at least 32 characters"):
            _validate_production_settings(settings)

    def test_dev_default_jwt_secret_warns_not_raises(self, monkeypatch: Any) -> None:
        """In development the default JWT secret must only warn, not raise."""
        monkeypatch.delenv("GLYPH_ENV", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        settings = GlyphSettings()
        # Must not raise.
        _validate_production_settings(settings)
        assert settings.jwt_secret_key == "change-me-in-production"

    def test_empty_jwt_secret_reset_to_default(self, monkeypatch: Any) -> None:
        """An empty/whitespace JWT secret is treated as unset (reset to default)."""
        monkeypatch.delenv("GLYPH_ENV", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        settings = GlyphSettings(jwt_secret_key="   ")
        _validate_production_settings(settings)
        assert settings.jwt_secret_key == "change-me-in-production"

    def test_prod_empty_jwt_secret_raises(self, monkeypatch: Any) -> None:
        """An empty JWT secret must trigger the production guard (via reset)."""
        monkeypatch.setenv("GLYPH_ENV", "production")
        settings = GlyphSettings(jwt_secret_key="")
        with pytest.raises(RuntimeError, match="JWT secret key must be changed from default"):
            _validate_production_settings(settings)


class TestProductionCipherKey:
    """Secret cipher key guard branch."""

    def test_prod_default_cipher_key_raises(self, monkeypatch: Any) -> None:
        """The default cipher key must be rejected in production."""
        monkeypatch.setenv("GLYPH_ENV", "production")
        settings = GlyphSettings(
            jwt_secret_key=_STRONG_JWT,
            secret_cipher_key="dev-secret-cipher-key-change-me",
            use_https=True,
        )
        with pytest.raises(RuntimeError, match="Secret cipher key must be changed from its default"):
            _validate_production_settings(settings)

    def test_dev_default_cipher_key_warns_not_raises(self, monkeypatch: Any) -> None:
        """In development the default cipher key must only warn, not raise."""
        monkeypatch.delenv("GLYPH_ENV", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        settings = GlyphSettings(
            jwt_secret_key=_STRONG_JWT,
            secret_cipher_key="dev-secret-cipher-key-change-me",
            use_https=True,
        )
        _validate_production_settings(settings)


class TestProductionHttps:
    """use_https guard branch."""

    def test_use_https_false_in_production_logs_critical(self, monkeypatch: Any) -> None:
        """use_https=False in production must emit a CRITICAL log (no raise)."""
        monkeypatch.setenv("GLYPH_ENV", "production")
        records: list[str] = []
        sink_id = logger.add(lambda message: records.append(str(message)), level="CRITICAL")
        try:
            settings = _make_settings(use_https=False)
            _validate_production_settings(settings)
        finally:
            logger.remove(sink_id)
        assert any("use_https is False in production" in record for record in records)

    def test_use_https_true_in_production_no_critical(self, monkeypatch: Any) -> None:
        """use_https=True in production must not emit the critical warning."""
        monkeypatch.setenv("GLYPH_ENV", "production")
        records: list[str] = []
        sink_id = logger.add(lambda message: records.append(str(message)), level="CRITICAL")
        try:
            _validate_production_settings(_make_settings(use_https=True))
        finally:
            logger.remove(sink_id)
        assert not any("use_https is False in production" in record for record in records)


class TestProductionHappyPath:
    """A fully hardened production configuration must pass validation."""

    def test_prod_valid_settings_pass(self, monkeypatch: Any) -> None:
        """Strong secrets + HTTPS must pass without raising or critical logs."""
        monkeypatch.setenv("GLYPH_ENV", "production")
        records: list[str] = []
        sink_id = logger.add(lambda message: records.append(str(message)), level="CRITICAL")
        try:
            _validate_production_settings(_make_settings())
        finally:
            logger.remove(sink_id)
        assert records == []


class TestSettingsSingleton:
    """get_settings / reload_settings singleton behavior."""

    def test_get_settings_returns_singleton(self, monkeypatch: Any) -> None:
        """Repeated get_settings calls must return the same instance."""
        original = settings_module._settings  # pyright: ignore[reportPrivateUsage]
        monkeypatch.delenv("GLYPH_ENV", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.setattr(settings_module, "_settings", None)  # pyright: ignore[reportPrivateUsage]
        try:
            first = settings_module.get_settings()
            second = settings_module.get_settings()
            assert first is second
        finally:
            settings_module._settings = original  # pyright: ignore[reportPrivateUsage]

    def test_reload_settings_returns_fresh_instance(self, monkeypatch: Any) -> None:
        """reload_settings must replace the cached instance with a new one.

        Runs in development mode: config.yml ships the default JWT secret and the
        YAML source outranks the environment in this project's source order, so a
        production reload would (correctly) refuse to start.
        """
        original = settings_module._settings  # pyright: ignore[reportPrivateUsage]
        monkeypatch.delenv("GLYPH_ENV", raising=False)
        monkeypatch.delenv("ENV", raising=False)
        monkeypatch.setattr(settings_module, "_settings", _make_settings())  # pyright: ignore[reportPrivateUsage]
        try:
            before = settings_module.get_settings()
            after = settings_module.reload_settings()
            assert after is not before
            assert settings_module.get_settings() is after  # pyright: ignore[reportPrivateUsage]
        finally:
            settings_module._settings = original  # pyright: ignore[reportPrivateUsage]

    def test_reload_settings_revalidates_production(self, monkeypatch: Any) -> None:
        """reload_settings must re-run production validation and raise on bad config."""
        original = settings_module._settings  # pyright: ignore[reportPrivateUsage]
        monkeypatch.setenv("GLYPH_ENV", "production")
        monkeypatch.setattr(settings_module, "_settings", _make_settings())  # pyright: ignore[reportPrivateUsage]
        try:
            with pytest.raises(RuntimeError, match="JWT secret key must be changed from default"):
                settings_module.reload_settings()
        finally:
            settings_module._settings = original  # pyright: ignore[reportPrivateUsage]
