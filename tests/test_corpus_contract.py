"""Corpus selection, diagnostics and CLI failure modes."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from pennovia.cli import _load_corpus
from pennovia.ingestion.reader import read_corpus, read_file


def words(label: str, count: int = 55) -> str:
    return " ".join([label] * count)


def test_read_file_rejects_unadvertised_extension(tmp_path):
    path = tmp_path / "notes.csv"
    path.write_text(words("sample"), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported corpus file format"):
        read_file(path)


def test_read_corpus_reports_rejected_inputs_on_stderr(tmp_path, capsys):
    ok = tmp_path / "ok.txt"
    short = tmp_path / "short.txt"
    bad = tmp_path / "bad.csv"
    ok.write_text(words("ok"), encoding="utf-8")
    short.write_text("two words", encoding="utf-8")
    bad.write_text(words("csv"), encoding="utf-8")
    assert read_corpus([ok, short, bad]) == [words("ok")]
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "short.txt" in captured.err
    assert "bad.csv" in captured.err
    assert "fewer than 51 words" in captured.err


def test_cli_corpus_is_deterministic_and_counts_only_usable(tmp_path, capsys):
    (tmp_path / "b.txt").write_text(words("second"), encoding="utf-8")
    (tmp_path / "a.txt").write_text(words("first"), encoding="utf-8")
    (tmp_path / "empty.txt").write_text("short", encoding="utf-8")
    (tmp_path / "folder.pdf").mkdir()
    texts, paths = _load_corpus(tmp_path)
    assert [Path(p).name for p in paths] == ["a.txt", "b.txt", "empty.txt"]
    assert texts == [words("first"), words("second")]
    assert "empty.txt" in capsys.readouterr().err


def test_cli_bad_profile_reports_error_without_traceback(tmp_path):
    profile = tmp_path / "corrupt.json"
    profile.write_text("{not json", encoding="utf-8")
    run = subprocess.run(
        [sys.executable, "-m", "pennovia.cli", "generate",
         "--profile", str(profile), "--topic", "test", "--backend", "ollama"],
        capture_output=True, text=True, check=False,
    )
    assert run.returncode == 1
    assert "ERROR:" in run.stderr
    assert "Traceback" not in run.stderr


def test_cli_analyze_reports_actual_file_count(tmp_path):
    input_dir = tmp_path / "corpus"
    input_dir.mkdir()
    (input_dir / "one.txt").write_text(words("this"), encoding="utf-8")
    (input_dir / "short.txt").write_text("short", encoding="utf-8")
    target = tmp_path / "profile.json"
    run = subprocess.run(
        [sys.executable, "-m", "pennovia.cli", "analyze",
         "--corpus", str(input_dir), "--out", str(target)],
        capture_output=True, text=True, check=False,
    )
    assert run.returncode == 0
    assert "1 usable of 2 files" in run.stdout
    assert json.loads(target.read_text(encoding="utf-8"))["text_count"] == 1
