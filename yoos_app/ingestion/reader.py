"""
Multi-format text reader.
Supports: PDF, HTML, TXT
"""
import os
import re
from pathlib import Path


def read_file(path: str) -> str:
    """Read a file and return clean plain text."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        return _read_pdf(path)
    elif ext in (".html", ".htm"):
        return _read_html(path)
    else:
        return p.read_text(encoding="utf-8", errors="replace")


def _read_pdf(path: str) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n\n".join(
                page.extract_text() or "" for page in pdf.pages
            ).strip()
    except ImportError:
        raise RuntimeError("PDF support requires: pip install pdfplumber")


def _read_html(path: str) -> str:
    try:
        from bs4 import BeautifulSoup
        html = Path(path).read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n")).strip()
    except ImportError:
        raise RuntimeError("HTML support requires: pip install beautifulsoup4")


def read_corpus(paths: list[str]) -> list[str]:
    """Read multiple files, return list of text strings."""
    texts = []
    for path in paths:
        try:
            text = read_file(path)
            if len(text.split()) > 50:
                texts.append(text)
        except Exception as e:
            print(f"  [skip] {path}: {e}")
    return texts
