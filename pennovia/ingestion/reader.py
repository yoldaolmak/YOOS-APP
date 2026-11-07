"""
Multi-format text reader.
Supports: PDF, HTML, TXT
"""
import ipaddress
import re
import socket
import sys
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPSConnection
from urllib3.connectionpool import HTTPSConnectionPool
from urllib3.exceptions import ConnectTimeoutError, NewConnectionError
from urllib3.util.connection import create_connection
from urllib.parse import urljoin, urlsplit
from typing import Iterable

SUPPORTED_EXTENSIONS = frozenset({".txt", ".html", ".htm", ".pdf"})
MIN_CORPUS_WORDS = 51


def read_file(path: str | Path) -> str:
    """Read a supported TXT, HTML or PDF file as plain text."""
    file_path = Path(path)
    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported corpus file format: {extension or '(none)'}")
    if extension == ".pdf":
        return _read_pdf(str(file_path))
    if extension in {".html", ".htm"}:
        return _read_html(str(file_path))
    return file_path.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: str) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n\n".join(
                page.extract_text() or "" for page in pdf.pages
            ).strip()
    except ImportError as exc:
        raise RuntimeError("PDF support requires: pip install pdfplumber") from exc


def _html_to_text(html: str, *, article_only: bool = False) -> str:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError("HTML support requires: pip install beautifulsoup4") from exc

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    root = (soup.find("article") or soup.find("main") or soup) if article_only else soup
    return re.sub(r"\n{3,}", "\n\n", root.get_text(separator="\n")).strip()


def _read_html(path: str) -> str:
    return _html_to_text(Path(path).read_text(encoding="utf-8", errors="replace"))


_MAX_URL_BYTES = 2 * 1024 * 1024
_MAX_URL_REDIRECTS = 3


def _check_article_url(url: str) -> None:
    """Accept ordinary public HTTPS article links, not local endpoints."""
    parts = urlsplit(url)
    try:
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port
    except ValueError as exc:
        raise ValueError("Invalid article URL") from exc
    if (parts.scheme != "https" or not host or parts.username is not None
            or parts.password is not None or port not in (None, 443)):
        raise ValueError("Article URLs must use public HTTPS without embedded credentials")
    if (host == "localhost" or "." not in host
            or host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))):
        raise ValueError("Local or internal article addresses are not allowed")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP-address article links are not allowed")


class _PublicHTTPSConnection(HTTPSConnection):
    """Connect to one checked IP, retaining the hostname for TLS verification."""

    def _new_conn(self):
        try:
            addresses = socket.getaddrinfo(
                self.host, self.port, type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise NewConnectionError(self, "Article hostname could not be resolved") from exc

        ips = {item[4][0] for item in addresses}
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise NewConnectionError(self, "Article hostname resolves to a non-public IP")

        # Connect to a validated numeric IP without changing self.host:
        # urllib3 must still verify TLS against the original hostname.
        try:
            return create_connection(
                (sorted(ips)[0], self.port),
                self.timeout,
                source_address=self.source_address,
                socket_options=self.socket_options,
            )
        except TimeoutError as exc:
            raise ConnectTimeoutError(self, "Article connection timed out") from exc
        except OSError as exc:
            raise NewConnectionError(self, "Could not connect to article host") from exc


class _PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _PublicHTTPSConnection


class _PublicHTTPSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            **self.poolmanager.pool_classes_by_scheme,
            "https": _PublicHTTPSPool,
        }


def read_url(url: str) -> str:
    """Fetch a single public HTML article (or plain text) with bounded resources.

    URLs are user-selected sources, not an automatic website crawler. Limit
    response size and redirect hops, and reject unsafe URL forms at each hop.
    """
    with requests.Session() as session:
        # Never inherit proxies from the process environment. The checked
        # direct-connection adapter must handle every article request.
        session.trust_env = False
        session.mount("https://", _PublicHTTPSAdapter())
        for _ in range(_MAX_URL_REDIRECTS + 1):
            _check_article_url(url)
            try:
                response = session.get(
                    url, timeout=(5, 15), stream=True, allow_redirects=False,
                    headers={"User-Agent": "Pennovia/0.2 (author voice corpus reader)"},
                )
            except requests.RequestException as exc:
                raise ValueError("Could not download article; check URL and connection") from exc
            try:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise ValueError("Article redirect has no destination")
                    url = urljoin(url, location)
                    continue
                try:
                    response.raise_for_status()
                except requests.RequestException as exc:
                    raise ValueError("Article URL returned an HTTP error") from exc

                mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if mime not in ("text/html", "application/xhtml+xml", "text/plain"):
                    raise ValueError("Article URL must return HTML or plain text")
                size = 0
                pieces = []
                try:
                    for piece in response.iter_content(chunk_size=65536):
                        size += len(piece)
                        if size > _MAX_URL_BYTES:
                            raise ValueError("Article response exceeds 2 MB")
                        pieces.append(piece)
                except requests.RequestException as exc:
                    raise ValueError("Article download interrupted") from exc
                encoding = response.encoding or "utf-8"
                try:
                    content = b"".join(pieces).decode(encoding, errors="replace")
                except LookupError as exc:
                    raise ValueError("Article has an unsupported text encoding") from exc
                return _html_to_text(content, article_only=True) if mime != "text/plain" else content.strip()
            finally:
                response.close()
        raise ValueError("Article redirected too many times")


def read_corpus(paths: Iterable[str | Path]) -> list[str]:
    """Read usable corpus files, warning on skipped inputs via stderr.

    A corrupt or unsupported input should not abort a batch with other
    usable files. Each returned text contains at least 51 whitespace tokens.
    """
    texts: list[str] = []
    for path in paths:
        try:
            text = read_file(path)
            if len(text.split()) < MIN_CORPUS_WORDS:
                print(f"  [skip] {path}: fewer than {MIN_CORPUS_WORDS} words", file=sys.stderr)
                continue
            texts.append(text)
        except Exception as exc:
            # Batch ingestion is intentionally best-effort; report failures.
            print(f"  [skip] {path}: {exc}", file=sys.stderr)
    return texts
