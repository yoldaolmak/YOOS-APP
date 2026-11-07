"""Offline public quality and security regression tests."""
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
from pennovia import __version__
from pennovia.exporter.writer import to_html, save_wordpress

def test_version_matches_package_metadata():
    metadata = (Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text()
    assert f'version = "{__version__}"' in metadata

def test_escaped_html():
    page = to_html("## <img src=x onerror=alert(1)>\n\n<script>alert(1)</script>", "<unsafe>")
    assert "&lt;unsafe&gt;" in page and "<script>" not in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page
    assert "&lt;script&gt;" in page

def test_wordpress_uses_https_and_body_fragment(monkeypatch):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'link': 'https://site.example/post'})
    monkeypatch.setitem(sys.modules, 'requests', SimpleNamespace(post=post))
    result = save_wordpress("<unsafe>", "Title", wp_url="https://site.example", wp_user="user", wp_password="secret")
    assert result == "https://site.example/post"
    url, kw = calls[0]
    assert url == "https://site.example/wp-json/wp/v2/posts"
    assert kw["verify"] is True and kw["json"]["status"] == "draft"
    assert kw["json"]["content"] == "<p>&lt;unsafe&gt;</p>"

def test_wordpress_rejects_insecure_endpoint(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, 'requests', SimpleNamespace(post=lambda *a, **kw: calls.append(1)))
    with pytest.raises(ValueError, match="HTTPS"):
        save_wordpress("Text", "Title", wp_url="http://site.example", wp_user="user", wp_password="secret")
    assert not calls

def test_public_release_points_to_existing_cli():
    root = Path(__file__).resolve().parents[1]
    ci = (root / '.github/workflows/ci.yml').read_text()
    docker = (root / 'Dockerfile').read_text()
    assert 'python -m pytest -q tests/' in ci
    assert 'ENTRYPOINT ["pennovia"]' in docker
    assert 'pennovia-server' not in (root / 'pyproject.toml').read_text()

def test_installed_demo_has_bundled_public_samples():
    import pennovia.demo
    corpus = Path(pennovia.demo.__file__).parent / 'corpus'
    assert len(list(corpus.glob('*.txt'))) == 3
