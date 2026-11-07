"""Safety regression tests for the opt-in Codex CLI backend."""
from types import SimpleNamespace
import subprocess

import pytest

from pennovia.voice import generator
from pennovia.voice.analyzer import VoiceProfile


def test_codex_is_confined_to_read_only_sandbox(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="  Draft text  ", stderr="")

    monkeypatch.setattr(generator.subprocess, "run", fake_run)
    result = generator.generate_codex(VoiceProfile(), "travel_blog", "A test topic")
    assert result == "Draft text"
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[:2] == ["codex", "exec"]
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    assert "--full-auto" not in command
    assert kwargs["capture_output"] is True
    assert kwargs["timeout"] == 600
    assert "A test topic" in kwargs["input"]


def test_codex_failure_does_not_disclose_stderr(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="TOKEN=secret-value")

    monkeypatch.setattr(generator.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Codex CLI failed") as exc:
        generator.generate_codex(VoiceProfile(), "story", "A topic")
    assert "secret-value" not in str(exc.value)


def test_codex_missing_cli_has_actionable_error(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("codex")

    monkeypatch.setattr(generator.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="not installed"):
        generator.generate_codex(VoiceProfile(), "story", "A topic")


def test_codex_timeout_has_actionable_error(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="codex", timeout=600)

    monkeypatch.setattr(generator.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="timed out"):
        generator.generate_codex(VoiceProfile(), "story", "A topic")
