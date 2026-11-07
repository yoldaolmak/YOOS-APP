"""Exercise real Pennovia CLI stages with synthetic provider replies; no API key/network."""
import sys
from pathlib import Path

import pytest
import requests

from pennovia import cli
from pennovia.voice.analyzer import VoiceProfile


# Original model-like output; used ONLY to simulate provider transport, not voice quality.
PARAGRAPHS = [
    (
        "A city unfolds through simple choices. Where should a visitor begin? "
        "The answer is rarely a single landmark. It begins with a street, a useful "
        "connection, and a little time to notice what changes from one neighborhood "
        "to another. But the obvious route is not always the most comfortable one. "
        "An ordinary afternoon may call for fewer stops and longer pauses."
    ),
    (
        "A good itinerary leaves some room. Crowded streets slow the pace, and "
        "long connections can consume more daylight than expected. It helps to "
        "choose one part of the city and explore it carefully rather than "
        "collecting locations on a list. For example, a short walk near a familiar "
        "square can provide enough context before moving on to the next district."
    ),
    (
        "However, the practical details matter. Check the actual operating hours "
        "before departure; do not assume that a service runs at the same frequency "
        "throughout the day. Leave time for unexpected delays, and consider "
        "where the return journey will begin. These choices are often more "
        "useful than another hurried stop or a promise of an experience that "
        "has not been verified."
    ),
    (
        "A final point deserves attention. Every guide has a point of view, "
        "and no itinerary fits every traveler. The best plan makes its limits "
        "visible, distinguishes what is known from what requires checking, "
        "and allows the reader to choose a comfortable pace. There is no "
        "need to invent personal stories in order to make practical writing "
        "engaging or clear. Simplicity can carry a voice too."
    ),
]
SYNTHETIC_DRAFT = "\n\n".join(PARAGRAPHS)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("synthetic remote failure")

    def json(self):
        return self.payload


@pytest.fixture
def offline_model(monkeypatch):
    """Route both provider and optional WP requests through a deterministic stub."""
    calls = []

    def post(url, **options):
        calls.append((url, options))
        if url == "https://openrouter.ai/api/v1/chat/completions":
            return FakeResponse({
                "id": "synthetic-completion",
                "choices": [{"message": {"role": "assistant", "content": SYNTHETIC_DRAFT}}],
            })
        if url == "https://synthetic.invalid/wp-json/wp/v2/posts":
            return FakeResponse({"id": 123, "link": "https://synthetic.invalid/?p=123"}, status=201)
        raise AssertionError("unexpected network destination")

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-placeholder-not-a-real-key")
    monkeypatch.setenv("WP_URL", "https://synthetic.invalid")
    monkeypatch.setenv("WP_USER", "synthetic-user")
    monkeypatch.setenv("WP_APP_PASSWORD", "synthetic-password")
    return calls


def invoke(monkeypatch, corpus, *args):
    monkeypatch.setattr(
        sys, "argv",
        ["pennovia", "run", "--corpus", str(corpus), "--author", "Synthetic Example",
         "--language", "en", "--type", "travel_guide", "--topic", "A city on foot",
         "--backend", "openrouter", *[str(a) for a in args]],
    )
    cli.main()


def demo_corpus():
    from pennovia import demo
    return Path(demo.__file__).parent / "corpus"


def test_cli_real_analyze_generate_audit_export_with_synthetic_provider(
    monkeypatch, offline_model, capsys, tmp_path
):
    output = tmp_path / "outputs"
    profile_file = tmp_path / "voice.json"

    invoke(
        monkeypatch, demo_corpus(),
        "--format", "html,txt,pdf", "--dest", output, "--save-profile", profile_file,
    )

    stdout = capsys.readouterr().out
    assert "[1/5] Reading writing samples" in stdout
    assert "[2/5] Analyzing voice" in stdout
    assert "[3/5] Generating" in stdout
    assert "[4/5] Auditing" in stdout
    assert "[5/5] Exporting" in stdout
    assert "Done. Score:" in stdout

    profile = VoiceProfile.load(profile_file)
    assert profile.text_count == 3
    assert profile.total_words > 600
    assert len(profile.sample_sentences) >= 3

    assert len(offline_model) == 1
    request_url, request = offline_model[0]
    assert request_url == "https://openrouter.ai/api/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer synthetic-placeholder-not-a-real-key"
    messages = request["json"]["messages"]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "A city on foot" in messages[1]["content"]
    assert "Sample sentences for rhythm" in messages[1]["content"]
    assert "Never invent firsthand visits" in messages[0]["content"]

    html_files = list(output.glob("*.html"))
    txt_files = list(output.glob("*.txt"))
    pdf_files = list(output.glob("*.pdf"))
    assert len(html_files) == len(txt_files) == len(pdf_files) == 1
    assert txt_files[0].read_text(encoding="utf-8") == SYNTHETIC_DRAFT
    html = html_files[0].read_text(encoding="utf-8")
    assert "A city unfolds through simple choices." in html
    assert "<html" in html
    assert pdf_files[0].read_bytes().startswith(b"%PDF")


def test_cli_synthetic_wordpress_export_defaults_to_draft(
    monkeypatch, offline_model, capsys
):
    invoke(monkeypatch, demo_corpus(), "--dest", "wordpress", "--format", "html")
    stdout = capsys.readouterr().out
    assert "WordPress draft: https://synthetic.invalid/?p=123" in stdout
    assert "Done. Score:" in stdout

    assert [url for url, _ in offline_model] == [
        "https://openrouter.ai/api/v1/chat/completions",
        "https://synthetic.invalid/wp-json/wp/v2/posts",
    ]
    post = offline_model[1][1]
    assert post["verify"] is True
    assert post["allow_redirects"] is False
    assert post["json"]["status"] == "draft"
    assert "A city unfolds through simple choices." in post["json"]["content"]


def test_cli_invalid_provider_reply_never_exports_or_claims_success(
    monkeypatch, offline_model, capsys, tmp_path
):
    def bad_reply(url, **options):
        assert url == "https://openrouter.ai/api/v1/chat/completions"
        return FakeResponse({"choices": [{"message": {"content": " "}}]})

    monkeypatch.setattr(requests, "post", bad_reply)
    output = tmp_path / "outputs"
    with pytest.raises(SystemExit) as exc:
        invoke(monkeypatch, demo_corpus(), "--format", "html,txt", "--dest", output)
    assert exc.value.code == 1
    assert not output.exists()
    captured = capsys.readouterr()
    assert "no usable draft text" in captured.err
    assert "Done. Score:" not in captured.out
    assert "Exporting" not in captured.out
