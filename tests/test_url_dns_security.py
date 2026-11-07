"""Article URLs must never connect to private DNS destinations."""
import socket

import pytest
import requests
from urllib3.exceptions import NewConnectionError

from pennovia.ingestion import reader
from pennovia.ingestion.reader import (
    _PublicHTTPSAdapter,
    _PublicHTTPSConnection,
    _PublicHTTPSPool,
    read_url,
)


def _answer(host, port, addresses):
    return [
        (socket.AF_INET6 if ":" in ip else socket.AF_INET,
         socket.SOCK_STREAM, 6, "", (ip, port))
        for ip in addresses
    ]


@pytest.mark.parametrize("addresses", [
    ["127.0.0.1"],
    ["10.10.10.2"],
    ["172.16.0.1"],
    ["192.168.1.1"],
    ["169.254.169.254"],
    ["100.64.0.1"],
    ["::1"],
    ["fc00::1"],
    ["fe80::1"],
    ["1.1.1.1", "192.168.0.1"],
    [],
])
def test_hostname_with_any_nonpublic_dns_answer_never_connects(
    monkeypatch, addresses
):
    calls = []
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, port, *, type: _answer(host, port, addresses),
    )
    monkeypatch.setattr(
        reader, "create_connection",
        lambda *args, **kwargs: calls.append(args),
    )
    connection = _PublicHTTPSConnection("articles.example.org", 443)
    with pytest.raises(NewConnectionError, match="non-public"):
        connection._new_conn()
    assert calls == []


def test_dns_rebinding_prevented_by_pinning_checked_ip(monkeypatch):
    names = []
    def resolve(host, port, *, type):
        names.append(host)
        return _answer(host, port, ["1.1.1.1"])
    monkeypatch.setattr(socket, "getaddrinfo", resolve)

    connected = []
    def connect(address, timeout, *, source_address, socket_options):
        connected.append(address)
        return "synthetic-socket"
    monkeypatch.setattr(reader, "create_connection", connect)

    connection = _PublicHTTPSConnection("articles.example.org", 443)
    assert connection._new_conn() == "synthetic-socket"
    assert names == ["articles.example.org"]
    assert connected == [("1.1.1.1", 443)]
    # Changing _dns_host also changes urllib3's host property: never do that.
    assert connection.host == "articles.example.org"
    assert connection._dns_host == "articles.example.org"


def test_failed_dns_lookup_is_not_retried_as_unchecked_connection(monkeypatch):
    def fail(host, port, *, type):
        raise socket.gaierror("resolution failure")
    monkeypatch.setattr(socket, "getaddrinfo", fail)
    connection = _PublicHTTPSConnection("articles.example.org", 443)
    with pytest.raises(NewConnectionError, match="could not be resolved"):
        connection._new_conn()


def test_article_session_disables_environment_proxies_and_uses_safe_pool(
    monkeypatch
):
    class Response:
        status_code = 200
        headers = {"Content-Type": "text/plain"}
        encoding = "utf-8"

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"An example text."

        def close(self):
            pass

    def get(self, url, **kwargs):
        assert self.trust_env is False
        adapter = self.get_adapter(url)
        assert isinstance(adapter, _PublicHTTPSAdapter)
        pool = adapter.poolmanager.connection_from_url(url)
        assert isinstance(pool, _PublicHTTPSPool)
        assert pool.ConnectionCls is _PublicHTTPSConnection
        assert kwargs["allow_redirects"] is False
        return Response()

    monkeypatch.setattr(requests.Session, "get", get)
    assert read_url("https://articles.example.org/post") == "An example text."
