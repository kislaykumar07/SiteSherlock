"""SSRF-safe URL validation (Blueprint section 8).

Blocks: non-http(s) schemes, credentials in URL, localhost names,
private / loopback / link-local / reserved / multicast IPs — checked on the
hostname's resolved addresses, and re-checked after redirects by the crawler.
"""
import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal", "metadata"}

_DNS_CACHE: dict[str, bool] = {}


def _resolve_safe(host: str) -> bool:
    """Cached DNS safety check — one resolution per host per process.
    (Uncached per-link resolution made serverless scans crawl.)"""
    if host in _DNS_CACHE:
        return _DNS_CACHE[host]
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        safe = all(not _ip_is_blocked(i[4][0]) for i in infos)
    except socket.gaierror:
        safe = False
    _DNS_CACHE[host] = safe
    return safe


_BLOCKED_NETS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",      # RFC1918 private
    "127.0.0.0/8",                                          # loopback
    "169.254.0.0/16",                                       # link-local (incl. cloud metadata)
    "0.0.0.0/8", "100.64.0.0/10",                           # unspecified / shared CGNAT
    "::1/128", "fe80::/10", "fc00::/7", "ff00::/8",         # v6 loopback/link-local/ULA/multicast
)]


def _ip_is_blocked(ip_str: str) -> bool:
    # NOTE: ipaddress.is_private is deliberately NOT used — in Python 3.12+ it
    # also flags benchmarking (198.18/15) and other non-internal ranges, which
    # false-blocks real public sites behind split-DNS / corporate proxies.
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return any(ip in net for net in _BLOCKED_NETS)


def validate_url(raw: str) -> tuple[str | None, str | None]:
    """Return (normalized_url, None) or (None, error_message)."""
    if not raw or not isinstance(raw, str):
        return None, "Enter a website URL."
    url = raw.strip()
    if "://" not in url:
        url = "https://" + url
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return None, "Only http:// and https:// websites can be scanned."
    if p.username or p.password:
        return None, "URLs with embedded usernames/passwords are not allowed."
    host = (p.hostname or "").lower()
    if not host:
        return None, "That URL does not contain a valid website host."
    if host in BLOCKED_HOSTNAMES or host.endswith(".local") or host.endswith(".internal"):
        return None, "Local and internal addresses cannot be scanned."
    # Literal IP?
    try:
        ip = ipaddress.ip_address(host)
        if _ip_is_blocked(str(ip)):
            return None, "Private and internal IP addresses cannot be scanned."
        return url, None
    except ValueError:
        pass
    if "." not in host:
        return None, "Enter a full website address, for example https://example.com"
    # Resolve and check every address (DNS-rebinding / SSRF defence in depth)
    if not _resolve_safe(host):
        # Distinguish "does not resolve" from "resolves to a blocked range"
        try:
            socket.getaddrinfo(host, 443 if p.scheme == "https" else 80, proto=socket.IPPROTO_TCP)
        except socket.gaierror:
            return None, f"Could not resolve {host}. Check the address and try again."
        return None, "That address resolves to a private/internal IP and cannot be scanned."
    return url, None


def host_is_safe(host: str) -> bool:
    """Re-check a (redirect) host before following it."""
    host = (host or "").lower()
    if not host or host in BLOCKED_HOSTNAMES or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not _ip_is_blocked(str(ip))
    except ValueError:
        pass
    return _resolve_safe(host)
