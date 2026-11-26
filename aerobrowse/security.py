"""URL policy and DNS-pinned transport; no implicit redirects or environment proxies."""

import http.client
import ipaddress
import re
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import idna

from aerobrowse.errors import AeroError

_dns_workers = ThreadPoolExecutor(max_workers=4, thread_name_prefix="aero-dns")
_dns_slots = threading.BoundedSemaphore(4)


@dataclass(frozen=True)
class Limits:
    url_chars: int = 8192
    response_bytes: int = 4 * 1024 * 1024
    body_bytes: int = 1024 * 1024
    timeout: float = 20.0
    redirects: int = 5
    html_nodes: int = 100_000
    html_depth: int = 128

    def __post_init__(self) -> None:
        if not (0 < self.timeout <= 120 and 0 <= self.redirects <= 10):
            raise ValueError("Invalid timeout or redirect limit")
        if any(
            v <= 0
            for v in (
                self.url_chars,
                self.response_bytes,
                self.body_bytes,
                self.html_nodes,
                self.html_depth,
            )
        ):
            raise ValueError("Limits must be positive")


@dataclass(frozen=True)
class Destination:
    url: str
    host: str
    port: int
    scheme: str
    addresses: tuple[str, ...]


class NetworkPolicy:
    def __init__(
        self, *, allow_networks: tuple[str, ...] = (), limits: Limits | None = None
    ):
        self.limits = limits or Limits()
        self.allow_networks = tuple(
            ipaddress.ip_network(n, strict=True) for n in allow_networks
        )

    def check_address(self, value: str) -> str:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise AeroError("INVALID_URL", "Invalid IP address") from exc
        special = isinstance(address, ipaddress.IPv6Address) and (
            address.ipv4_mapped is not None
            or address.sixtofour is not None
            or address.teredo is not None
            or address in ipaddress.ip_network("64:ff9b::/96")
        )
        allowed = any(
            address in n for n in self.allow_networks if n.version == address.version
        )
        if (
            special
            or (not address.is_global or address.is_multicast or address.is_reserved)
            and not allowed
        ):
            raise AeroError(
                "BLOCKED_DESTINATION", "Destination is not permitted by network policy"
            )
        return str(address)

    def validate(self, url: str, timeout: float | None = None) -> Destination:
        if not isinstance(url, str) or not url or len(url) > self.limits.url_chars:
            raise AeroError("INVALID_URL", "URL is empty or exceeds the length limit")
        if re.search(r"[\x00-\x20\x7f\\]", url):
            raise AeroError("INVALID_URL", "URL contains prohibited characters")
        try:
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                raise ValueError("scheme")
            if parts.username is not None or "%" in parts.hostname:
                raise ValueError("credentials or zone")
            host = parts.hostname.rstrip(".").lower()
            port = parts.port or (443 if parts.scheme == "https" else 80)
            if not 1 <= port <= 65535:
                raise ValueError("port")
            try:
                literal = ipaddress.ip_address(host)
            except ValueError:
                literal = None
            if literal is None:
                host = idna.encode(host, uts46=True, std3_rules=True).decode("ascii")
                if "." not in host or host.endswith(
                    (".localhost", ".local", ".internal", ".home", ".lan")
                ):
                    raise AeroError(
                        "BLOCKED_DESTINATION", "Internal hostnames are not permitted"
                    )
                if re.fullmatch(r"[0-9.]+", host) or any(
                    p.startswith("0x") for p in host.split(".")
                ):
                    raise ValueError("alternate IP notation")
                addresses = self._resolve(host, port, timeout or self.limits.timeout)
            else:
                host, addresses = str(literal), (str(literal),)
            checked = tuple(sorted({self.check_address(a) for a in addresses}))
            if not checked:
                raise AeroError("DNS_ERROR", "DNS returned no usable addresses")
            authority = f"[{host}]" if ":" in host else host
            normalized = urlunsplit(
                (
                    parts.scheme,
                    f"{authority}:{port}",
                    parts.path or "/",
                    parts.query,
                    "",
                )
            )
            return Destination(normalized, host, port, parts.scheme, checked)
        except (ValueError, UnicodeError, idna.IDNAError) as exc:
            raise AeroError("INVALID_URL", "URL is malformed or unsupported") from exc

    @staticmethod
    def _resolve(host: str, port: int, timeout: float) -> tuple[str, ...]:
        if not _dns_slots.acquire(blocking=False):
            raise AeroError("DNS_BUSY", "DNS capacity exhausted")
        future = _dns_workers.submit(
            socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM
        )
        future.add_done_callback(lambda _: _dns_slots.release())
        try:
            return tuple(str(item[4][0]) for item in future.result(timeout=timeout))
        except FutureTimeout as exc:
            raise AeroError("TIMEOUT", "DNS resolution timed out") from exc
        except OSError as exc:
            raise AeroError("DNS_ERROR", "DNS resolution failed") from exc


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(self, target: Destination, timeout: float):
        super().__init__(target.host, target.port, timeout=timeout)
        self.target = target

    def connect(self) -> None:
        address = self.target.addresses[0]
        sock = socket.socket(
            socket.AF_INET6 if ":" in address else socket.AF_INET, socket.SOCK_STREAM
        )
        try:
            sock.settimeout(self.timeout)
            sock.connect((address, self.target.port))
            if self.target.scheme == "https":
                sock = ssl.create_default_context().wrap_socket(
                    sock, server_hostname=self.target.host
                )
            self.sock = sock
        except BaseException:
            sock.close()
            raise


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes


class SafeTransport:
    def __init__(self, policy: NetworkPolicy | None = None):
        self.policy = policy or NetworkPolicy()

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: bytes = b"",
        follow_redirects: bool = True,
    ) -> Response:
        limits = self.policy.limits
        if len(body) > limits.body_bytes:
            raise AeroError("REQUEST_TOO_LARGE", "Request body exceeds limit")
        if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
            raise AeroError("INVALID_REQUEST", "Unsupported HTTP method")
        safe = {
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.5",
            "Accept-Encoding": "identity",
        }
        for key, value in (headers or {}).items():
            if key.lower() in {
                "accept",
                "accept-language",
                "content-type",
                "user-agent",
            }:
                if len(value) > 8192 or "\r" in value or "\n" in value:
                    raise AeroError("INVALID_REQUEST", "Invalid request header")
                safe[key] = value
        deadline = time.monotonic() + limits.timeout
        try:
            for hop in range(limits.redirects + 1):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AeroError("TIMEOUT", "Request deadline exceeded")
                target = self.policy.validate(url, remaining)
                conn = _PinnedConnection(
                    target, max(0.001, deadline - time.monotonic())
                )
                try:
                    parts = urlsplit(target.url)
                    conn.request(
                        method,
                        urlunsplit(("", "", parts.path, parts.query, "")),
                        body=body,
                        headers=safe,
                    )
                    response = conn.getresponse()
                    response_headers = {
                        k.lower(): v
                        for k, v in response.getheaders()
                        if k.lower()
                        not in {"set-cookie", "authorization", "proxy-authorization"}
                    }
                    if response.status in {301, 302, 303, 307, 308}:
                        location = response.getheader("Location")
                        if not location:
                            raise AeroError(
                                "INVALID_REDIRECT", "Redirect has no destination"
                            )
                        if hop == limits.redirects:
                            raise AeroError(
                                "TOO_MANY_REDIRECTS", "Redirect limit exceeded"
                            )
                        url = urljoin(target.url, location)
                        validated = self.policy.validate(
                            url, max(0.001, deadline - time.monotonic())
                        )
                        if not follow_redirects:
                            response_headers["location"] = validated.url
                            return Response(
                                target.url, response.status, response_headers, b""
                            )
                        if (
                            response.status == 303
                            or response.status in {301, 302}
                            and method == "POST"
                        ):
                            method, body = "GET", b""
                        continue
                    if response.getheader(
                        "Content-Encoding", "identity"
                    ).lower() not in {"identity", ""}:
                        raise AeroError(
                            "UNSUPPORTED_ENCODING",
                            "Compressed responses are not accepted",
                        )
                    length = response.getheader("Content-Length")
                    if length and int(length) > limits.response_bytes:
                        raise AeroError("RESPONSE_TOO_LARGE", "Response exceeds limit")
                    chunks = bytearray()
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise AeroError("TIMEOUT", "Request deadline exceeded")
                        if conn.sock:
                            conn.sock.settimeout(remaining)
                        chunk = response.read1(
                            min(65536, limits.response_bytes + 1 - len(chunks))
                        )
                        if not chunk:
                            break
                        chunks.extend(chunk)
                        if len(chunks) > limits.response_bytes:
                            raise AeroError(
                                "RESPONSE_TOO_LARGE", "Response exceeds limit"
                            )
                    return Response(
                        target.url, response.status, response_headers, bytes(chunks)
                    )
                finally:
                    conn.close()
        except TimeoutError as exc:
            raise AeroError("TIMEOUT", "Network operation timed out") from exc
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise AeroError("NETWORK_ERROR", "Network request failed") from exc
        raise AeroError("NETWORK_ERROR", "Request did not complete")
