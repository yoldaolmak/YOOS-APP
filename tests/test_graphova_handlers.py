"""
Tests for graphova.utils.file_handlers.
All tests run without API keys.
"""
from __future__ import annotations
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from graphova.utils.file_handlers import (
    read_file, read_bytes, read_corpus, read_corpus_bytes,
    is_allowed_path, ALLOWED_EXTENSIONS, MAX_FILE_BYTES,
)

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "corpus")


# ── is_allowed_path ────────────────────────────────────────────────────────────

def test_allowed_path_no_base():
    assert is_allowed_path("/tmp/file.txt") is True

def test_allowed_path_inside_base():
    assert is_allowed_path("/tmp/sub/file.txt", "/tmp") is True

def test_allowed_path_outside_base():
    assert is_allowed_path("/etc/passwd", "/tmp") is False

def test_allowed_path_traversal():
    assert is_allowed_path("/tmp/../etc/passwd", "/tmp") is False


# ── read_file ─────────────────────────────────────────────────────────────────

def test_read_file_txt():
    path = os.path.join(CORPUS_DIR, "twain_01.txt")
    if not os.path.exists(path):
        pytest.skip("Twain corpus not available")
    text = read_file(path)
    assert len(text.split()) > 50

def test_read_file_html():
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False,
                                     encoding="utf-8") as f:
        f.write("<html><body><h1>Test</h1><p>Paragraph text here.</p></body></html>")
        tmp = f.name
    try:
        text = read_file(tmp)
        assert "Test" in text
        assert "Paragraph" in text
    finally:
        os.unlink(tmp)

def test_read_file_empty():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        tmp = f.name
    try:
        text = read_file(tmp)
        assert text == ""
    finally:
        os.unlink(tmp)

def test_read_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_file("/tmp/definitely_does_not_exist_graphova.txt")

def test_read_file_unsupported_extension():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("a,b,c")
        tmp = f.name
    try:
        with pytest.raises(ValueError, match="Unsupported"):
            read_file(tmp)
    finally:
        os.unlink(tmp)

def test_read_file_too_large():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="wb", delete=False) as f:
        f.write(b"x" * (MAX_FILE_BYTES + 1))
        tmp = f.name
    try:
        with pytest.raises(ValueError, match="too large"):
            read_file(tmp)
    finally:
        os.unlink(tmp)

def test_read_file_not_a_file():
    with pytest.raises(ValueError, match="Not a file"):
        read_file(CORPUS_DIR)


# ── read_bytes ────────────────────────────────────────────────────────────────

def test_read_bytes_txt():
    data = b"Hello world. This is a test. " * 10
    text = read_bytes(data, "test.txt")
    assert "Hello world" in text

def test_read_bytes_html():
    data = b"<html><body><p>Test HTML content</p></body></html>"
    text = read_bytes(data, "test.html")
    assert "Test HTML content" in text

def test_read_bytes_unsupported():
    with pytest.raises(ValueError, match="Unsupported"):
        read_bytes(b"data", "file.csv")

def test_read_bytes_too_large():
    data = b"x" * (MAX_FILE_BYTES + 1)
    with pytest.raises(ValueError, match="too large"):
        read_bytes(data, "file.txt")

def test_read_bytes_encoding_error():
    """Invalid UTF-8 bytes should be replaced, not crash."""
    data = b"Hello \xff\xfe world"
    text = read_bytes(data, "file.txt")
    assert "Hello" in text
    assert "world" in text


# ── read_corpus ───────────────────────────────────────────────────────────────

def test_read_corpus_basic():
    paths = [
        os.path.join(CORPUS_DIR, f)
        for f in ["twain_01.txt", "twain_02.txt", "twain_03.txt"]
        if os.path.exists(os.path.join(CORPUS_DIR, f))
    ]
    if not paths:
        pytest.skip("Twain corpus not available")
    texts = read_corpus(paths)
    assert len(texts) == len(paths)
    assert all(len(t.split()) >= 50 for t in texts)

def test_read_corpus_skips_short():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("Too short.")
        tmp = f.name
    try:
        texts = read_corpus([tmp])
        assert len(texts) == 0  # filtered — < 50 words
    finally:
        os.unlink(tmp)

def test_read_corpus_skips_missing_file():
    texts = read_corpus(["/nonexistent/file.txt"])
    assert texts == []

def test_read_corpus_mixed():
    with tempfile.TemporaryDirectory() as d:
        txt_path = os.path.join(d, "a.txt")
        html_path = os.path.join(d, "b.html")
        bad_path = os.path.join(d, "c.csv")

        with open(txt_path, "w") as f:
            f.write(" ".join(["word"] * 100))
        with open(html_path, "w") as f:
            f.write("<html><body><p>" + " ".join(["text"] * 100) + "</p></body></html>")
        with open(bad_path, "w") as f:
            f.write("a,b,c")

        texts = read_corpus([txt_path, html_path, bad_path])
        assert len(texts) == 2  # csv skipped


# ── read_corpus_bytes ─────────────────────────────────────────────────────────

def test_read_corpus_bytes_basic():
    files = [
        ("doc1.txt", (" ".join(["word"] * 100)).encode()),
        ("doc2.txt", (" ".join(["text"] * 100)).encode()),
    ]
    texts = read_corpus_bytes(files)
    assert len(texts) == 2

def test_read_corpus_bytes_skips_short():
    files = [("tiny.txt", b"Too short.")]
    texts = read_corpus_bytes(files)
    assert len(texts) == 0

def test_read_corpus_bytes_skips_unsupported():
    files = [("data.csv", b"a,b,c" * 100)]
    texts = read_corpus_bytes(files)
    assert len(texts) == 0

def test_read_corpus_bytes_html():
    html = ("<html><body><p>" + " ".join(["word"] * 100) + "</p></body></html>").encode()
    texts = read_corpus_bytes([("page.html", html)])
    assert len(texts) == 1
    assert "word" in texts[0]


# ── HTML cleaning ─────────────────────────────────────────────────────────────

def test_html_strips_scripts():
    html = b"<html><body><p>Content here is good.</p><script>evil()</script></body></html>"
    text = read_bytes(html, "page.html")
    assert "evil" not in text
    assert "Content here" in text

def test_html_strips_nav():
    html_str = """<html><body>
      <nav><a>Home</a><a>About</a></nav>
      <p>""" + "Real content here. " * 10 + """</p>
      <footer>Copyright</footer>
    </body></html>"""
    text = read_bytes(html_str.encode(), "page.html")
    assert "Copyright" not in text
    assert "Real content here" in text
