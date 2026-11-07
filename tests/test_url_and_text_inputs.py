"""URL and paste inputs must work through the existing analysis/pipeline CLI."""
import io
import sys
from pathlib import Path

import pytest
import requests

from pennovia import cli
from pennovia.ingestion.reader import read_url
from pennovia.voice.analyzer import VoiceProfile


SAMPLE = (
    "Ben yazarken gördüğüm yerleri anlatmayı seviyorum ama acele etmeden. "
    "Sokakları yürümek insanın dikkatini başka bir yöne çeviriyor. "
    "Bir şehre geldiğimde önce yolun nasıl ilerlediğine bakıyorum. "
    "Kalabalık bazen yorucu oluyor, ancak küçük ayrıntılar daha sonra aklımda kalıyor. "
    "Bu yüzden kısa yolları değil kendi ritmimi tercih ediyorum. "
) * 3


class Page:
    def __init__(self, content, status=200, mime="text/html", location=None):
        self.content = content.encode("utf-8")
        self.status_code = status
        self.headers = {"Content-Type": mime}
        if location:
            self.headers["Location"] = location
        self.encoding = "utf-8"
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("simulated response failure")

    def iter_content(self, chunk_size=65536):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start:start + chunk_size]

    def close(self):
        self.closed = True


def html_sample():
    return (
        "<html><head><title>Site</title></head><body>"
        "<nav>Ignore this navigation menu</nav>"
        "<main><article><h1>Yolun ritmi</h1><p>" + SAMPLE + "</p></article></main>"
        "<footer>Do not count footer material</footer>"
        "<script>ignoreThisInstruction();</script>"
        "</body></html>"
    )


def test_read_url_extracts_article_not_page_chrome(monkeypatch):
    page = Page(html_sample())
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return page
    monkeypatch.setattr(requests, "get", get)
    text = read_url("https://example.org/blog/yazim")
    assert "Yolun ritmi" in text
    assert "Ben yazarken" in text
    assert "Ignore this navigation menu" not in text
    assert "Do not count footer material" not in text
    assert "ignoreThisInstruction" not in text
    assert page.closed
    assert calls[0][1]["stream"] is True
    assert calls[0][1]["allow_redirects"] is False


def test_url_can_follow_canonical_https_redirect(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return Page("", status=301, location="https://www.example.org/article")
        return Page(html_sample())
    monkeypatch.setattr(requests, "get", get)
    assert "Ben yazarken" in read_url("https://example.org/article")
    assert calls == ["https://example.org/article", "https://www.example.org/article"]


@pytest.mark.parametrize("url", [
    "http://example.org/article", "file:///etc/passwd",
    "https://localhost/private", "https://host.internal/page",
    "https://127.0.0.1/article", "https://[::1]/article",
    "https://user:secret@example.org/article", "https://example.org:8443/article",
])
def test_unsafe_url_is_rejected_before_http(monkeypatch, url):
    calls = []
    monkeypatch.setattr(requests, "get", lambda *a, **kw: calls.append(a) or Page(""))
    with pytest.raises(ValueError):
        read_url(url)
    assert calls == []


def test_https_redirect_to_unsafe_destination_is_rejected(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append(url)
        return Page("", status=302, location="http://localhost/private")
    monkeypatch.setattr(requests, "get", get)
    with pytest.raises(ValueError, match="public HTTPS"):
        read_url("https://example.org/article")
    assert calls == ["https://example.org/article"]


@pytest.mark.parametrize("page,expected", [
    (Page("<html/>", mime="application/pdf"), "HTML or plain text"),
    (Page("x" * (2 * 1024 * 1024 + 1)), "exceeds 2 MB"),
    (Page("", status=404), "HTTP error"),
])
def test_bad_remote_content_is_rejected_and_closed(monkeypatch, page, expected):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: page)
    with pytest.raises(ValueError, match=expected):
        read_url("https://example.org/article")
    assert page.closed


def test_analyze_accepts_url_and_paste_without_local_files(monkeypatch, tmp_path):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: Page(html_sample()))
    profile_file = tmp_path / "writer.json"
    monkeypatch.setattr(sys, "argv", [
        "pennovia", "analyze",
        "--url", "https://example.org/article",
        "--text", SAMPLE, "--author", "Yazar", "--language", "tr",
        "--out", str(profile_file),
    ])
    cli.main()
    profile = VoiceProfile.load(profile_file)
    assert profile.text_count == 2
    assert profile.language == "tr"
    assert profile.total_words >= 102


def test_analyze_reads_pasted_multiline_stdin(monkeypatch, tmp_path):
    target = tmp_path / "writer.json"
    monkeypatch.setattr(sys, "stdin", io.StringIO(SAMPLE))
    monkeypatch.setattr(sys, "argv", [
        "pennovia", "analyze", "--text", "-", "--out", str(target),
    ])
    cli.main()
    assert VoiceProfile.load(target).text_count == 1


def test_bad_url_can_be_skipped_when_valid_pasted_writing_exists(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: Page("", status=404))
    target = tmp_path / "writer.json"
    monkeypatch.setattr(sys, "argv", [
        "pennovia", "analyze",
        "--url", "https://example.org/not-found",
        "--text", SAMPLE,
        "--out", str(target),
    ])
    cli.main()
    assert VoiceProfile.load(target).text_count == 1
    assert "Skipping URL #1" in capsys.readouterr().err


def test_missing_sources_or_only_short_text_fails_without_profile(
    monkeypatch, tmp_path
):
    target = tmp_path / "voice.json"
    for extras in ([], ["--text", "Too short"]):
        monkeypatch.setattr(sys, "argv", [
            "pennovia", "analyze", "--out", str(target), *extras,
        ])
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1
        assert not target.exists()


def test_run_url_and_paste_through_synthetic_provider_to_exports(
    monkeypatch, tmp_path
):
    from pennovia.voice import generator

    monkeypatch.setattr(requests, "get", lambda *a, **kw: Page(html_sample()))
    draft = " ".join(
        ["A practical city guide can be short and clear without invented visits."]
        * 24
    )
    def fake_generate(profile, content_type, topic, backend, **kwargs):
        assert profile.text_count == 2
        assert profile.language == "tr"
        assert content_type == "travel_guide"
        assert topic == "Yeni bir gezi"
        return draft
    monkeypatch.setattr(generator, "generate", fake_generate)

    target = tmp_path / "exports"
    monkeypatch.setattr(sys, "argv", [
        "pennovia", "run", "--url", "https://example.org/article",
        "--text", SAMPLE, "--language", "tr", "--type", "travel_guide",
        "--topic", "Yeni bir gezi", "--backend", "ollama",
        "--format", "html,txt", "--dest", str(target),
    ])
    cli.main()
    assert len(list(target.glob("*.html"))) == 1
    outputs = list(target.glob("*.txt"))
    assert len(outputs) == 1
    assert outputs[0].read_text(encoding="utf-8") == draft
