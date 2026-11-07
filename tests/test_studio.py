"""Studio's real local HTTP surface, from writing samples to exported drafts."""
import base64
import http.client
import json
import threading
from contextlib import contextmanager

import pytest
import requests

from pennovia.studio import server


TEXT = " ".join(
    ["Every journey begins with an ordinary decision about the next street. "
     "But practical details make the difference between an interesting day "
     "and an exhausting one."] * 5
)
DRAFT = "\n\n".join(
    ["Every place requires a useful plan, but the plan should leave room for change. "
     "Practical details can help without turning an ordinary story into a list."] * 10
)


@contextmanager
def running_studio():
    local = server.make_server(0)
    worker = threading.Thread(target=local.serve_forever, daemon=True)
    worker.start()
    try:
        yield local
    finally:
        local.shutdown()
        worker.join(timeout=5)
        local.server_close()


def request(local, method, path, payload=None, *, token=None, headers=None):
    port = local.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = dict(headers or {})
    if method == "POST":
        h.setdefault("Content-Type", "application/json")
        if token is not None:
            h["X-Pennovia-Token"] = token
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    else:
        body = None
    try:
        conn.request(method, path, body=body, headers=h)
        response = conn.getresponse()
        data = response.read()
        return response.status, data, dict(response.getheaders())
    finally:
        conn.close()


def post_json(local, path, data, *, token=None, headers=None):
    status, payload, info = request(
        local, "POST", path, data, token=token or local.studio_token, headers=headers,
    )
    if info["Content-Type"].startswith("application/json"):
        return status, json.loads(payload)
    return status, payload


def test_studio_serves_packaged_assets_and_has_local_only_security_headers():
    with running_studio() as local:
        code, page, h = request(local, "GET", "/")
        assert code == 200
        markup = page.decode("utf-8")
        assert "Pennovia Studio" in markup
        assert local.studio_token in markup
        assert "app.js" in markup
        assert "app.css" in markup
        assert h["Cache-Control"] == "no-store"
        assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
        for asset, expected in [
            ("/app.js", b"/api/analyze"),
            ("/app.css", b".workbench"),
        ]:
            status, content, _ = request(local, "GET", asset)
            assert status == 200
            assert expected in content
        assert request(local, "GET", "/no-such-file")[0] == 404


def test_request_requires_local_host_session_token_and_same_origin():
    with running_studio() as local:
        port = local.server_address[1]
        assert request(local, "GET", "/", headers={"Host": "evil.example"})[0] == 403
        payload = {"profile": {}}
        # Missing token is not an authorization bypass.
        assert request(local, "POST", "/api/profile", payload)[0] == 403
        assert request(
            local, "POST", "/api/profile", payload,
            token="incorrect-token",
        )[0] == 403
        assert request(
            local, "POST", "/api/profile", payload, token=local.studio_token,
            headers={"Origin": "https://evil.example"},
        )[0] == 403
        assert request(
            local, "POST", "/api/profile", payload, token=local.studio_token,
            headers={"Host": f"evil.example:{port}"},
        )[0] == 403


def test_studio_profile_combines_text_html_file_and_article_url(monkeypatch):
    looked_up = []
    def read_url(url):
        looked_up.append(url)
        return TEXT
    monkeypatch.setattr(server, "read_url", read_url)

    with running_studio() as local:
        sources = [
            {"type": "text", "value": TEXT},
            {"type": "url", "value": "https://example.org/story"},
            {
                "type": "file", "name": "article.html",
                "data": base64.b64encode((
                    "<html><nav>Skip menu</nav><article><p>" + TEXT +
                    "</p></article></html>"
                ).encode("utf-8")).decode("ascii"),
            },
            {"type": "text", "value": "Not enough words"},
        ]
        code, result = post_json(local, "/api/analyze", {
            "sources": sources, "author": "Local Writer", "language": "en",
        })
        assert code == 200
        assert result["profile"]["text_count"] == 3
        assert result["profile"]["author_name"] == "Local Writer"
        assert result["accepted"] == 3
        assert result["profile"]["total_words"] >= 150
        assert looked_up == ["https://example.org/story"]
        assert len(result["warnings"]) == 1
        assert "Sample 4" in result["warnings"][0]

        status, loaded = post_json(local, "/api/profile", {
            "profile": result["profile"],
        })
        assert status == 200
        assert loaded["profile"] == result["profile"]


def test_studio_end_to_end_synthetic_model_to_review_and_three_downloads(monkeypatch):
    posted = []
    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": DRAFT}}]}

    def synthetic_post(url, **kwargs):
        posted.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr(requests, "post", synthetic_post)
    monkeypatch.setenv("OPENROUTER_API_KEY", "not-a-real-api-key")

    with running_studio() as local:
        code, profile_data = post_json(local, "/api/analyze", {
            "sources": [{"type": "text", "value": TEXT}],
            "author": "Writer", "language": "en",
        })
        assert code == 200
        profile = profile_data["profile"]
        code, generated = post_json(local, "/api/generate", {
            "profile": profile, "topic": "A coastal city",
            "content_type": "travel_guide", "backend": "openrouter",
        })
        assert code == 200
        assert generated["draft"] == DRAFT
        assert generated["review"]["score"] >= 0
        assert posted[0][0] == "https://openrouter.ai/api/v1/chat/completions"
        sent = posted[0][1]["json"]["messages"]
        assert sent[0]["role"] == "system"
        assert "A coastal city" in sent[1]["content"]
        assert "Sample sentences for rhythm" in sent[1]["content"]

        status, reviewed = post_json(local, "/api/review", {
            "profile": profile, "draft": DRAFT + " Another sentence.",
        })
        assert status == 200
        assert 0 <= reviewed["score"] <= 100

        for ext, marker in [
            ("txt", DRAFT.encode("utf-8")[:30]),
            ("html", b"<!DOCTYPE html>"),
            ("pdf", b"%PDF"),
        ]:
            status, exported = post_json(local, "/api/export", {
                "profile": profile, "draft": DRAFT, "title": "Coastal City",
                "format": ext, "destination": "download",
            })
            assert status == 200
            assert marker in exported


def test_studio_wordpress_sends_draft_only_and_never_publishes(monkeypatch):
    from pennovia.exporter import writer

    calls = []
    def capture(content, title, publish=False):
        calls.append((title, publish, content))
        return "https://example.org/?p=123"
    monkeypatch.setattr(writer, "save_wordpress", capture)

    with running_studio() as local:
        profile = post_json(local, "/api/analyze", {
            "sources": [{"type": "text", "value": TEXT}],
            "author": "Writer",
        })[1]["profile"]
        status, data = post_json(local, "/api/export", {
            "profile": profile, "draft": DRAFT, "title": "Coastal City",
            "format": "html", "destination": "wordpress", "publish": True,
        })
        assert status == 200
        assert data["url"] == "https://example.org/?p=123"
        assert calls == [("Coastal City", False, DRAFT)]


@pytest.mark.parametrize("payload", [
    {"sources": [], "author": "Writer"},
    {"sources": [{"type": "text", "value": "Too short"}], "author": "Writer"},
    {"sources": [{"type": "file", "name": "bad.exe", "data": "YWJj"}], "author": "Writer"},
    {"sources": [{"type": "url", "value": "http://localhost"}], "author": "Writer"},
])
def test_bad_source_cannot_create_an_empty_profile(monkeypatch, payload):
    from pennovia import studio
    assert studio is not None
    with running_studio() as local:
        code, result = post_json(local, "/api/analyze", payload)
        assert code == 400
        assert "error" in result


def test_invalid_model_response_returns_error_without_saved_draft(monkeypatch):
    from pennovia.voice import generator

    monkeypatch.setattr(
        generator, "generate", lambda *a, **kw: (_ for _ in ()).throw(
            RuntimeError("OpenRouter returned no usable draft text")
        ),
    )
    with running_studio() as local:
        profile = post_json(local, "/api/analyze", {
            "sources": [{"type": "text", "value": TEXT}],
            "author": "Writer",
        })[1]["profile"]
        code, data = post_json(local, "/api/generate", {
            "profile": profile, "topic": "A town", "content_type": "story",
            "backend": "openrouter",
        })
        assert code == 400
        assert "no usable draft text" in data["error"]


def test_invalid_profile_and_unsupported_export_are_rejected():
    with running_studio() as local:
        assert post_json(local, "/api/profile", {
            "profile": {"language": "invalid"},
        })[0] == 400
        assert post_json(local, "/api/export", {
            "profile": {}, "draft": DRAFT, "title": "title",
            "format": "exe", "destination": "download",
        })[0] == 400


@pytest.mark.parametrize("key,value", [
    ("backend", []), ("backend", {"name": "ollama"}),
    ("content_type", []), ("content_type", {"name": "travel_guide"}),
])
def test_invalid_generation_options_return_400_not_server_error(key, value):
    with running_studio() as local:
        profile = post_json(local, "/api/analyze", {
            "sources": [{"type": "text", "value": TEXT}], "author": "Writer",
        })[1]["profile"]
        payload = {
            "profile": profile, "topic": "An ordinary destination",
            "content_type": "travel_guide", "backend": "ollama",
        }
        payload[key] = value
        status, result = post_json(local, "/api/generate", payload)
        assert status == 400
        assert "Select a supported" in result["error"]


def test_studio_disallows_non_loopback_config_and_invalid_port():
    with pytest.raises(ValueError):
        server.make_server(-1)
    with pytest.raises(ValueError):
        server.make_server(65536)
