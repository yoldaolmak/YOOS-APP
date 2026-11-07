"""Pennovia release identity and packaging consistency checks."""
from importlib.metadata import version
from pathlib import Path

import pennovia


def test_distributable_version_matches_module():
    assert version("pennovia") == pennovia.__version__ == "0.2.0"


def test_public_brand_matches_product_entrypoints():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    docker = (root / "Dockerfile").read_text(encoding="utf-8")
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert readme.startswith("# Pennovia")
    assert 'name = "pennovia"' in project
    assert 'pennovia = "pennovia.cli:main"' in project
    assert 'ENTRYPOINT ["pennovia"]' in docker
    assert "pennovia --version" in ci
    assert "python -m pennovia.demo" in ci


def test_demo_output_environment_variable_has_consistent_name():
    root = Path(__file__).resolve().parents[1]
    demo = (root / "pennovia/demo/__main__.py").read_text(encoding="utf-8")
    assert 'PENNOVIA_DEMO_OUTPUT_DIR' in demo


def test_demo_topic_matches_bundled_mock_text():
    root = Path(__file__).resolve().parents[1]
    demo = (root / "pennovia/demo/__main__.py").read_text(encoding="utf-8")
    assert 'topic = "Istanbul, Turkey"' in demo
    assert 'explicit_local_backend = backend in ("ollama", "codex")' in demo


def test_cli_honors_named_backend_environment_variable():
    root = Path(__file__).resolve().parents[1]
    cli = (root / "pennovia/cli.py").read_text(encoding="utf-8")
    assert cli.count('default=os.environ.get("PENNOVIA_BACKEND", "auto")') == 2
