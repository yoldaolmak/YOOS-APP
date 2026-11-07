"""Provider adapters must never treat missing or blank data as publishable content."""
import sys
from types import SimpleNamespace

import pytest

from pennovia.voice import generator
from pennovia.voice.analyzer import VoiceProfile


PROFILE = VoiceProfile(language="en")


def test_blank_and_nontext_responses_are_not_drafts():
    for value in (None, "", "   ", [], {}):
        with pytest.raises(RuntimeError, match="no usable draft"):
            generator._require_draft(value, "Mock")
    assert generator._require_draft("  Draft  ", "Mock") == "Draft"


def test_ollama_rejects_empty_and_malformed_json(monkeypatch):
    class FakeRequestError(Exception):
        pass
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"message": {"content": "   "}}

    monkeypatch.setitem(
        sys.modules, "requests",
        SimpleNamespace(post=lambda *a, **kw: Response(), RequestException=FakeRequestError),
    )
    with pytest.raises(RuntimeError, match="no usable draft"):
        generator.generate_ollama(PROFILE, "story", "Topic")


def test_ollama_network_failure_is_actionable_without_echoing_secrets(monkeypatch):
    class FakeRequestError(Exception):
        pass
    def fail(*args, **kwargs):
        raise FakeRequestError("authorization-token-secret")
    monkeypatch.setitem(
        sys.modules, "requests",
        SimpleNamespace(post=fail, RequestException=FakeRequestError),
    )
    with pytest.raises(RuntimeError, match="Ollama request failed") as exc:
        generator.generate_ollama(PROFILE, "story", "Topic")
    assert "authorization-token-secret" not in str(exc.value)


def test_openrouter_malformed_reply_is_rejected(monkeypatch):
    class FakeRequestError(Exception):
        pass
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": []}
    monkeypatch.setitem(
        sys.modules, "requests",
        SimpleNamespace(post=lambda *a, **kw: Response(), RequestException=FakeRequestError),
    )
    with pytest.raises(RuntimeError, match="invalid response structure"):
        generator.generate_openrouter(PROFILE, "story", "Topic", api_key="fake")


def test_openai_none_content_is_rejected(monkeypatch):
    def fake_client(**kwargs):
        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=lambda **kw: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
                )
            ))
        )
    monkeypatch.setitem(
        sys.modules, "openai",
        SimpleNamespace(OpenAI=fake_client, OpenAIError=Exception),
    )
    with pytest.raises(RuntimeError, match="no usable draft"):
        generator.generate_openai(PROFILE, "story", "Topic", api_key="fake")


def test_anthropic_joins_text_blocks_and_skips_nontext(monkeypatch):
    def fake_client(**kwargs):
        return SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: SimpleNamespace(
            content=[
                SimpleNamespace(type="tool_use", text=None),
                SimpleNamespace(type="text", text="First part."),
                SimpleNamespace(type="text", text="Second part."),
            ]
        )))
    monkeypatch.setitem(
        sys.modules, "anthropic",
        SimpleNamespace(Anthropic=fake_client, AnthropicError=Exception),
    )
    assert generator.generate_anthropic(PROFILE, "story", "Topic", api_key="fake") == "First part.\nSecond part."


def test_auto_does_not_hide_programming_errors_as_missing_backend(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def raise_unexpected(*args, **kwargs):
        raise TypeError("Unexpected programming error")

    monkeypatch.setattr(generator, "generate_ollama", raise_unexpected)
    with pytest.raises(TypeError, match="Unexpected programming error"):
        generator.generate(PROFILE, "story", "Topic", backend="auto")
