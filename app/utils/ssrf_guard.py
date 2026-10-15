"""SSRF guard for outbound server-side requests.

Glyph lets users configure an arbitrary OpenAI-compatible LLM ``base_url`` that is
then requested *server-side* (connection test, finding analysis). Without a guard,
an attacker can point that URL at loopback, RFC1918, link-local (the cloud
metadata service at ``169.254.169.254``), reserved, or multicast ranges and use
the server as a proxy to probe internal networks.

This module is the last line of defense at request time. It is self-contained:
it re-validates the URL and the resolved addresses even though config-time
validation already enforces scheme/hostname/port, because the guard must not
depend on any upstream check having run.

Two entry points are provided:

* :func:`assert_public_url` -- resolve the host and raise ``ValueError`` if any
  resolved address is not public.
* :func:`resolve_and_pin` -- resolve, validate, and return a *pinned* URL that
  connects directly to a validated IP (with the original ``Host`` header
  preserved). Pinning is the DNS-rebinding mitigation: the address is resolved
  and validated once, and the connection is made to that exact IP rather than
  re-resolving the hostname at connect time.
"""

import asyncio
import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit

# Schemes that may be requested server-side. Anything else (file://, gopher://,
# ftp://, ...) is rejected outright.
_ALLOWED_SCHEMES = {"http", "https"}

# Carrier-grade NAT (RFC 6598). Not always flagged by ``is_private`` across
# Python versions, so it is rejected explicitly.
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _is_public(ip_str: str) -> bool:
    """Return True if ``ip_str`` is a public, routable, non-special address.

    Rejects loopback, private (RFC1918 + CGNAT), link-local (incl. the cloud
    metadata range 169.254/16 and fe80::/10), reserved, multicast, and
    unspecified addresses.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return False
    return not (isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT)


def _resolve_addresses(host: str, port: int) -> list[str]:
    """Blocking DNS resolution returning a de-duplicated list of IP strings.

    Runs in a worker thread (see :func:`_resolve_async`); it must never be
    called directly from the event loop.
    """
    infos = socket.getaddrinfo(
        host,
        port,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )
    seen: set[str] = set()
    addrs: list[str] = []
    for info in infos:
        # For SOCK_STREAM the first sockaddr element is the host (IPv4/IPv6).
        addr = str(info[4][0])
        if addr not in seen:
            seen.add(addr)
            addrs.append(addr)
    return addrs


async def _resolve_async(host: str, port: int) -> list[str]:
    """Resolve ``host`` off the event loop, mapping failures to ``ValueError``."""
    try:
        return await asyncio.to_thread(_resolve_addresses, host, port)
    except (socket.gaierror, OSError, UnicodeError):
        raise ValueError("host does not resolve") from None


def _parse_public(url: str) -> tuple[Any, str, int]:
    """Parse ``url`` and return ``(parts, host, effective_port)``.

    Raises:
        ValueError: If the scheme is not http/https or the hostname is missing.
    """
    parts = urlsplit(url)
    if parts.scheme not in _ALLOWED_SCHEMES:
        raise ValueError("unsupported URL scheme")
    host = parts.hostname
    if not host:
        raise ValueError("URL has no hostname")
    scheme_default = 443 if parts.scheme == "https" else 80
    port = parts.port if parts.port is not None else scheme_default
    return parts, host, port


async def assert_public_url(url: str) -> None:
    """Resolve the URL's host and reject non-public destinations.

    Args:
        url: The fully qualified endpoint URL to validate.

    Raises:
        ValueError: If the host is missing, does not resolve, or resolves to a
            loopback / private / link-local / reserved / multicast address. The
            message is intentionally generic so callers do not leak which range
            matched.
    """
    _parts, host, port = _parse_public(url)
    addrs = await _resolve_async(host, port)
    if not addrs:
        raise ValueError("host does not resolve")
    for addr in addrs:
        if not _is_public(addr):
            raise ValueError("host resolves to a non-public address")


async def resolve_and_pin(url: str) -> tuple[str, str]:
    """Validate ``url`` and return ``(pinned_url, host_header)``.

    The hostname is resolved and every resolved address is validated as public.
    The returned ``pinned_url`` connects directly to the first validated address
    (IPv6 bracketed) while preserving the original scheme, path, and query. The
    returned ``host_header`` is the original host (with port when non-default)
    so the virtual host the server expects is preserved.

    Pinning to the validated IP is the DNS-rebinding mitigation: the connection
    is made to the exact address that was validated, not to a re-resolved
    hostname at connect time.

    Args:
        url: The fully qualified endpoint URL to pin.

    Returns:
        A tuple of (pinned_url, host_header).

    Raises:
        ValueError: If the host is missing, does not resolve, or resolves to a
            non-public address.
    """
    parts, host, port = _parse_public(url)
    addrs = await _resolve_async(host, port)
    if not addrs:
        raise ValueError("host does not resolve")
    for addr in addrs:
        if not _is_public(addr):
            raise ValueError("host resolves to a non-public address")

    ip = addrs[0]
    host_part = f"[{ip}]:{port}" if ":" in ip else f"{ip}:{port}"
    pinned = f"{parts.scheme}://{host_part}{parts.path}"
    if parts.query:
        pinned += f"?{parts.query}"

    scheme_default = 443 if parts.scheme == "https" else 80
    host_header = f"{host}:{port}" if port != scheme_default else host
    return pinned, host_header
