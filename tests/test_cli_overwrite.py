"""CLI draft/profile outputs must require explicit replacement intent."""
import subprocess
import sys
from types import SimpleNamespace

import pytest

from pennovia import cli
from pennovia.voice.analyzer import VoiceProfile
from pennovia.voice import generator


def test_api_save_can_reject_overwrite(tmp_path):
    profile = tmp_path / "voice.json"
    profile.write_text("keep this", encoding="utf-8")
    with pytest.raises(FileExistsError):
        VoiceProfile(author_name="Writer").save(profile, overwrite=False)
    assert profile.read_text(encoding="utf-8") == "keep this"


def test_api_save_default_is_backward_compatible(tmp_path):
    profile = tmp_path / "voice.json"
    profile.write_text("old", encoding="utf-8")
    VoiceProfile(author_name="Writer").save(profile)
    assert "Writer" in profile.read_text(encoding="utf-8")


def test_cli_analyze_requires_overwrite_flag(tmp_path):
    corpus = tmp_path / "corpus.txt"
    corpus.write_text(" ".join(["words"] * 70), encoding="utf-8")
    target = tmp_path / "profile.json"
    target.write_text("original", encoding="utf-8")
    command = [
        sys.executable, "-m", "pennovia.cli", "analyze",
        "--corpus", str(corpus), "--out", str(target),
    ]
    denied = subprocess.run(command, capture_output=True, text=True, check=False)
    assert denied.returncode == 1
    assert "--overwrite" in denied.stderr
    assert target.read_text(encoding="utf-8") == "original"

    accepted = subprocess.run(command + ["--overwrite"], capture_output=True, text=True, check=False)
    assert accepted.returncode == 0, accepted.stderr
    assert "schema_version" in target.read_text(encoding="utf-8")


def test_generate_does_not_call_external_backend_if_output_exists(tmp_path, monkeypatch):
    profile = tmp_path / "voice.json"
    VoiceProfile(author_name="Writer").save(profile)
    draft = tmp_path / "draft.txt"
    draft.write_text("original draft", encoding="utf-8")

    def unexpected(*args, **kwargs):
        raise AssertionError("Backend must not run when output would be overwritten")

    monkeypatch.setattr(generator, "generate", unexpected)
    args = SimpleNamespace(
        profile=str(profile), type="story", topic="Example", backend="openai",
        model=None, out=str(draft), overwrite=False, verbose=False,
    )
    with pytest.raises(SystemExit) as exc:
        cli.cmd_generate(args)
    assert exc.value.code == 1
    assert draft.read_text(encoding="utf-8") == "original draft"


def test_generate_can_explicitly_overwrite_existing_draft(tmp_path, monkeypatch):
    profile = tmp_path / "voice.json"
    VoiceProfile(author_name="Writer", avg_sentence_words=8).save(profile)
    draft = tmp_path / "draft.txt"
    draft.write_text("original", encoding="utf-8")
    monkeypatch.setattr(generator, "generate", lambda *a, **kw: "A new first draft with some words.")
    args = SimpleNamespace(
        profile=str(profile), type="story", topic="Example", backend="openai",
        model=None, out=str(draft), overwrite=True, verbose=False,
    )
    cli.cmd_generate(args)
    assert draft.read_text(encoding="utf-8") == "A new first draft with some words."
