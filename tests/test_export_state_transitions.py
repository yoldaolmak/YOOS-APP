"""CLI export outcomes: all-or-nothing for local files, explicit partial remote writes."""
from types import SimpleNamespace

import pytest

from pennovia import cli
from pennovia.exporter import writer


def test_local_multi_format_export_cleans_up_files_after_later_failure(tmp_path, monkeypatch, capsys):
    source = tmp_path / "input.txt"
    source.write_text("The original author text stays unchanged.", encoding="utf-8")
    real_save = writer.save_local

    def save_then_fail(content, title, fmt, destination):
        if fmt == "pdf":
            raise RuntimeError("synthetic PDF failure")
        return real_save(content, title, fmt, destination)

    monkeypatch.setattr(writer, "save_local", save_then_fail)
    args = SimpleNamespace(
        input=str(source), title="My text", format="txt,pdf",
        dest=str(tmp_path), publish=False,
    )
    with pytest.raises(SystemExit) as caught:
        cli.cmd_export(args)
    assert caught.value.code == 1
    assert list(tmp_path.iterdir()) == [source]
    captured = capsys.readouterr()
    assert "Created files from this attempt were removed" in captured.err
    assert "Saved (txt)" not in captured.out


def test_remote_multi_export_reports_completed_uploads_before_ambiguous_error(
    tmp_path, monkeypatch, capsys,
):
    draft = tmp_path / "draft.txt"
    draft.write_text("Original text", encoding="utf-8")
    calls = []

    def fake_drive(content, title, fmt):
        calls.append(fmt)
        if fmt == "pdf":
            raise writer.RemoteOutcomeUnknown("Drive response lost; status unknown")
        return "https://drive.example/already-created"

    monkeypatch.setattr(writer, "save_google_drive", fake_drive)
    args = SimpleNamespace(
        input=str(draft), title="Sample", format="txt,pdf",
        dest="google_drive", publish=False,
    )
    with pytest.raises(SystemExit) as caught:
        cli.cmd_export(args)
    assert caught.value.code == 1
    assert calls == ["txt", "pdf"]
    message = capsys.readouterr().err
    assert "Already completed remotely" in message
    assert "Remote outcome unknown" in message
    assert "https://drive.example/already-created" in message


def test_run_does_not_save_profile_if_model_generation_fails(tmp_path, monkeypatch):
    from pennovia.voice import generator

    monkeypatch.setattr(
        generator, "generate",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("model unavailable")),
    )
    args = SimpleNamespace(
        corpus=None, urls=[], texts=["I write about ordinary roads and their details. " * 12],
        author="Writer", language="en", type="travel_blog", topic="A town",
        backend="ollama", model=None, format="txt", dest=str(tmp_path),
        save_profile=str(tmp_path / "profile.json"), overwrite=False,
        publish=False,
    )
    with pytest.raises(SystemExit):
        cli.cmd_run(args)
    assert not (tmp_path / "profile.json").exists()
    assert list(tmp_path.iterdir()) == []


def test_remote_unknown_is_runtime_error_type():
    exc = writer.RemoteOutcomeUnknown("unknown")
    assert isinstance(exc, RuntimeError)
