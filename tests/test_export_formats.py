"""Destination format rules must be explicit before network operations."""
from types import SimpleNamespace

import pytest

from pennovia import cli
from pennovia.exporter import writer


def test_wordpress_export_rejects_multiple_formats_before_upload(tmp_path, monkeypatch):
    source = tmp_path / "draft.txt"
    source.write_text("Draft", encoding="utf-8")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("must not contact WordPress")

    monkeypatch.setattr(writer, "save_wordpress", fail_if_called)
    args = SimpleNamespace(input=str(source), title="Draft", format="html,txt", dest="wordpress", publish=False)
    with pytest.raises(SystemExit) as exc:
        cli.cmd_export(args)
    assert exc.value.code == 1


def test_wordpress_single_html_makes_exactly_one_request(tmp_path, monkeypatch):
    source = tmp_path / "draft.txt"
    source.write_text("Draft", encoding="utf-8")
    calls = []
    monkeypatch.setattr(
        writer, "save_wordpress",
        lambda content, title, publish=False: calls.append((content, title, publish)) or "https://example.test/draft",
    )
    args = SimpleNamespace(input=str(source), title="Draft", format="html", dest="wordpress", publish=False)
    cli.cmd_export(args)
    assert calls == [("Draft", "Draft", False)]


def test_run_rejects_wordpress_formats_before_corpus_and_model_calls(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("must not start pipeline")

    monkeypatch.setattr(cli, "_load_corpus", unexpected)
    args = SimpleNamespace(format="html,pdf", dest="wordpress", save_profile=None)
    with pytest.raises(SystemExit):
        cli.cmd_run(args)


@pytest.mark.parametrize("raw", ["html,html", "html,exe", "html,", ""])
def test_invalid_formats_are_rejected(raw):
    with pytest.raises(SystemExit):
        cli._export_formats(raw, "downloads", "html")


def test_wordpress_and_local_defaults_are_distinct():
    assert cli._export_formats(None, "wordpress", "html") == ["html"]
    assert cli._export_formats(None, "downloads", "html,txt") == ["html", "txt"]
