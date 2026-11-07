"""Remote writes are not safely retryable after a lost or malformed response."""
from types import SimpleNamespace

import pytest
import requests

from pennovia.exporter import writer
from tests.test_studio import TEXT, post_json, running_studio


def _wp_response(status=201, payload=None):
    return SimpleNamespace(
        status_code=status,
        raise_for_status=lambda: None,
        json=lambda: {"link": "https://example.org/draft"} if payload is None else payload,
    )


def _wordpress(monkeypatch, result):
    def fake_post(url, **kwargs):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(requests, "post", fake_post)
    return lambda: writer.save_wordpress(
        "Text", "Title", wp_url="https://example.org",
        wp_user="author", wp_password="private",
    )


@pytest.mark.parametrize("result", [
    requests.ReadTimeout("response never arrived"),
    requests.ConnectionError("connection dropped"),
    _wp_response(503),
    _wp_response(payload={}),
])
def test_wordpress_request_may_have_succeeded_after_missing_response(monkeypatch, result):
    export = _wordpress(monkeypatch, result)
    with pytest.raises(writer.RemoteOutcomeUnknown, match="before retrying"):
        export()


def test_wordpress_explicit_rejection_is_not_ambiguous(monkeypatch):
    result = _wp_response(401)
    result.raise_for_status = lambda: (_ for _ in ()).throw(
        requests.HTTPError("401 Unauthorized")
    )
    export = _wordpress(monkeypatch, result)
    with pytest.raises(RuntimeError, match="WordPress export failed") as err:
        export()
    assert not isinstance(err.value, writer.RemoteOutcomeUnknown)


def test_studio_remote_unknown_returns_explicit_409_without_claiming_failure(monkeypatch):
    def maybe_saved(*args, **kwargs):
        raise writer.RemoteOutcomeUnknown("Check the destination before retrying")

    monkeypatch.setattr(writer, "save_wordpress", maybe_saved)
    with running_studio() as local:
        status, analyzed = post_json(local, "/api/analyze", {
            "sources": [{"type": "text", "value": TEXT}], "author": "Writer",
        })
        assert status == 200
        status, result = post_json(local, "/api/export", {
            "profile": analyzed["profile"],
            "draft": TEXT,
            "title": "Draft",
            "destination": "wordpress",
            "format": "html",
        })
        assert status == 409
        assert result["outcome"] == "unknown"
        assert "Check the destination" in result["error"]


def test_studio_rejects_empty_imported_profile():
    with running_studio() as local:
        status, result = post_json(local, "/api/profile", {"profile": {}})
        assert status == 400
        assert "no analyzed writing" in result["error"]
