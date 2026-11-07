"""Automatic provider selection is deterministic; no silent cross-cloud retry."""
import pytest

from pennovia.voice import generator
from pennovia.voice.analyzer import VoiceProfile


def test_auto_provider_failure_does_not_send_to_another_service(monkeypatch):
    called = []

    def reject(*args, **kwargs):
        called.append("anthropic")
        raise RuntimeError("Synthetic upstream failure")

    def unexpected(*args, **kwargs):
        called.append("openrouter")
        return "Should never appear"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic")
    monkeypatch.setattr(generator, "generate_anthropic", reject)
    monkeypatch.setattr(generator, "generate_openrouter", unexpected)

    with pytest.raises(RuntimeError, match="Synthetic upstream failure"):
        generator.generate(VoiceProfile(), "story", "A subject", backend="auto")
    assert called == ["anthropic"]
