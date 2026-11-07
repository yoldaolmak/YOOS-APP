"""Local exports should not silently overwrite drafts or leak temp PDFs."""
from pathlib import Path
import subprocess
import sys

import pytest

from pennovia.exporter import writer


def test_repeated_local_exports_never_replace_previous_work(tmp_path):
    first = writer.save_local("First version", "Repeated Title", "txt", str(tmp_path))
    second = writer.save_local("Second version", "Repeated Title", "txt", str(tmp_path))
    assert first != second
    assert Path(first).read_text(encoding="utf-8") == "First version"
    assert Path(second).read_text(encoding="utf-8") == "Second version"


def test_invalid_local_format_is_rejected_before_file_creation(tmp_path):
    with pytest.raises(ValueError, match="Unsupported export format"):
        writer.save_local("Content", "Title", "../../bad", str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_generated_pdf_paths_are_unique(tmp_path, monkeypatch):
    monkeypatch.setattr(writer.tempfile, "tempdir", str(tmp_path))
    first = writer.to_pdf("First PDF", "Same title")
    second = writer.to_pdf("Second PDF", "Same title")
    try:
        assert first != second
        assert Path(first).stat().st_size > 500
        assert Path(second).stat().st_size > 500
    finally:
        Path(first).unlink(missing_ok=True)
        Path(second).unlink(missing_ok=True)


def test_failed_export_does_not_leave_empty_reserved_file(tmp_path, monkeypatch):
    def fail_pdf(*args, **kwargs):
        raise RuntimeError("PDF failed")

    monkeypatch.setattr(writer, "to_pdf", fail_pdf)
    with pytest.raises(RuntimeError, match="PDF failed"):
        writer.save_local("Content", "Title", "pdf", str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_cli_reports_unsupported_export_format_without_traceback(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text("Draft", encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable, "-m", "pennovia.cli", "export",
            "--input", str(source), "--title", "Draft",
            "--format", "../invalid", "--dest", str(tmp_path),
        ],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 1
    assert "Unsupported export format" in result.stderr
    assert "Traceback" not in result.stderr
