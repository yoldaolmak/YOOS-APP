"""WordPress credentials and drafts must never follow unexpected redirects."""
from types import SimpleNamespace

import pytest
import requests

from pennovia.exporter.writer import save_wordpress


def response(*, status=201, payload=None, http_error=None):
    def raise_for_status():
        if http_error is not None:
            raise http_error
    return SimpleNamespace(
        status_code=status,
        raise_for_status=raise_for_status,
        json=lambda: {"link": "https://example.test/?p=1"} if payload is None else payload,
    )


def send(monkeypatch, result):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(requests, "post", fake_post)
    return calls


def export(**kwargs):
    return save_wordpress(
        "Draft text", "Draft title",
        wp_url="https://example.test", wp_user="author", wp_password="private",
        **kwargs,
    )


def test_success_posts_once_as_draft_with_https_verification(monkeypatch):
    calls = send(monkeypatch, response())
    assert export() == "https://example.test/?p=1"
    assert len(calls) == 1
    url, options = calls[0]
    assert url == "https://example.test/wp-json/wp/v2/posts"
    assert options["auth"] == ("author", "private")
    assert options["verify"] is True
    assert options["allow_redirects"] is False
    assert options["json"]["status"] == "draft"


def test_publish_remains_explicit(monkeypatch):
    calls = send(monkeypatch, response())
    export(publish=True)
    assert calls[0][1]["json"]["status"] == "publish"


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_redirects_are_refused_without_following(monkeypatch, status):
    calls = send(monkeypatch, response(status=status))
    with pytest.raises(RuntimeError, match="redirected"):
        export()
    assert len(calls) == 1


@pytest.mark.parametrize("input_url", [
    "http://example.test",
    "https://author:pass@example.test",
    "https://example.test?secret=foo",
    "https://example.test/#fragment",
])
def test_invalid_base_urls_are_rejected_before_request(monkeypatch, input_url):
    calls = send(monkeypatch, response())
    with pytest.raises(ValueError, match="HTTPS base URL"):
        save_wordpress("Draft", "Title", wp_url=input_url, wp_user="user", wp_password="private")
    assert calls == []


@pytest.mark.parametrize("bad_payload", [{}, {"link": None}, {"link": ""}, [], "not an object"])
def test_malformed_success_response_is_not_reported_as_export(monkeypatch, bad_payload):
    send(monkeypatch, response(payload=bad_payload))
    with pytest.raises(RuntimeError, match="invalid post response"):
        export()


def test_malformed_json_is_reported_without_response_data(monkeypatch):
    result = response()
    result.json = lambda: (_ for _ in ()).throw(ValueError("raw-remote-secret"))
    send(monkeypatch, result)
    with pytest.raises(RuntimeError, match="invalid post response") as exc:
        export()
    assert "raw-remote-secret" not in str(exc.value)


def test_network_and_http_errors_are_bounded(monkeypatch):
    send(monkeypatch, requests.ConnectionError("secret-token"))
    with pytest.raises(RuntimeError, match="WordPress export failed") as exc:
        export()
    assert "secret-token" not in str(exc.value)

    send(monkeypatch, response(status=401, http_error=requests.HTTPError("secret-token")))
    with pytest.raises(RuntimeError, match="WordPress export failed") as exc:
        export()
    assert "secret-token" not in str(exc.value)
