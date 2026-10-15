"""Tests for the SSRF guard (app/utils/ssrf_guard.py)."""

import socket
from typing import Any

import pytest
from app.utils import ssrf_guard

# Addresses that must be rejected as non-public.
NON_PUBLIC_HOSTS = [
    pytest.param("127.0.0.1", id="loopback-v4"),
    pytest.param("::1", id="loopback-v6"),
    pytest.param("169.254.169.254", id="cloud-metadata"),
    pytest.param("10.0.0.1", id="rfc1918-10"),
    pytest.param("172.16.0.1", id="rfc1918-172"),
    pytest.param("192.168.1.1", id="rfc1918-192"),
    pytest.param("0.0.0.0", id="unspecified"),
    pytest.param("100.64.0.1", id="cgnat"),
    pytest.param("fe80::1", id="link-local-v6"),
]

# Public addresses that must be accepted.
PUBLIC_HOSTS = [
    pytest.param("93.184.216.34", id="public-v4"),
    pytest.param("2606:2800:220:1:248:1893:25c8:1946", id="public-v6"),
]


def _fake_getaddrinfo(ip: str) -> Any:
    """Build a getaddrinfo stand-in that resolves to a single ``ip``."""

    def _getaddrinfo(host: str, port: int, *args: Any, **kwargs: Any) -> list[tuple]:
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET,
                 socket.SOCK_STREAM, socket.IPPROTO_TCP, (), (ip, port))]

    return _getaddrinfo


class TestAssertPublicUrl:
    """Tests for assert_public_url."""

    @pytest.mark.parametrize("host", NON_PUBLIC_HOSTS)
    async def test_rejects_non_public(self, monkeypatch: Any, host: str) -> None:
        """Non-public resolved addresses raise ValueError."""
        monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", _fake_getaddrinfo(host))

        with pytest.raises(ValueError):
            await ssrf_guard.assert_public_url(f"http://{host}/v1/chat/completions")

    @pytest.mark.parametrize("host", PUBLIC_HOSTS)
    async def test_accepts_public(self, monkeypatch: Any, host: str) -> None:
        """Public resolved addresses are accepted."""
        monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", _fake_getaddrinfo(host))

        host_part = f"[{host}]" if ":" in host else host
        await ssrf_guard.assert_public_url(f"http://{host_part}/v1/chat/completions")

    async def test_rejects_unresolvable_host(self, monkeypatch: Any) -> None:
        """A host that fails to resolve raises ValueError."""

        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise socket.gaierror("name resolution failed")

        monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", _boom)

        with pytest.raises(ValueError, match="does not resolve"):
            await ssrf_guard.assert_public_url("http://no-such-host.invalid/v1")

    async def test_rejects_bad_scheme(self) -> None:
        """Non-http(s) schemes are rejected before any resolution."""
        with pytest.raises(ValueError, match="scheme"):
            await ssrf_guard.assert_public_url("file:///etc/passwd")

    async def test_rejects_missing_hostname(self) -> None:
        """A URL with no hostname is rejected before any resolution."""
        with pytest.raises(ValueError, match="hostname"):
            await ssrf_guard.assert_public_url("http:///v1")

    async def test_rejects_if_any_address_non_public(self, monkeypatch: Any) -> None:
        """A host resolving to a mix of public and private is rejected."""

        def _mixed(host: str, port: int, *args: Any, **kwargs: Any) -> list[tuple]:
            return [
                (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, (), ("93.184.216.34", port)),
                (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, (), ("127.0.0.1", port)),
            ]

        monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", _mixed)

        with pytest.raises(ValueError):
            await ssrf_guard.assert_public_url("http://mixed.example/v1")


class TestResolveAndPin:
    """Tests for resolve_and_pin."""

    async def test_pins_http_to_validated_ip(self, monkeypatch: Any) -> None:
        """An http URL is pinned to the validated IP with the host header preserved."""
        monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))

        pinned, host_header = await ssrf_guard.resolve_and_pin("http://example.com:8080/v1/chat")

        assert pinned == "http://93.184.216.34:8080/v1/chat"
        assert host_header == "example.com:8080"

    async def test_pins_preserves_query(self, monkeypatch: Any) -> None:
        """The query string is preserved when pinning."""
        monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))

        pinned, _ = await ssrf_guard.resolve_and_pin("http://example.com/v1?api=1")

        assert pinned == "http://93.184.216.34:80/v1?api=1"

    async def test_brackets_ipv6(self, monkeypatch: Any) -> None:
        """An IPv6 pinned address is bracketed."""
        monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", _fake_getaddrinfo("2606:2800:220:1:248:1893:25c8:1946"))

        pinned, host_header = await ssrf_guard.resolve_and_pin("http://example.com/v1")

        assert pinned == "http://[2606:2800:220:1:248:1893:25c8:1946]:80/v1"
        assert host_header == "example.com"

    async def test_rejects_non_public(self, monkeypatch: Any) -> None:
        """A non-public resolved address raises ValueError."""
        monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", _fake_getaddrinfo("169.254.169.254"))

        with pytest.raises(ValueError):
            await ssrf_guard.resolve_and_pin("http://169.254.169.254/latest/meta-data/")

    async def test_rejects_unresolvable(self, monkeypatch: Any) -> None:
        """A host that fails to resolve raises ValueError."""

        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise socket.gaierror("nope")

        monkeypatch.setattr(ssrf_guard.socket, "getaddrinfo", _boom)

        with pytest.raises(ValueError, match="does not resolve"):
            await ssrf_guard.resolve_and_pin("http://nope.invalid/v1")
