"""
Multi-format text reader.
Supports: PDF, HTML, TXT
"""
import re
import sys
from pathlib import Path
from typing import Iterable

SUPPORTED_EXTENSIONS = frozenset({".txt", ".html", ".htm", ".pdf"})
MIN_CORPUS_WORDS = 51


def read_file(path: str | Path) -> str:
    """Read a supported TXT, HTML or PDF file as plain text."""
    file_path = Path(path)
    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported corpus file format: {extension or '(none)'}")
    if extension == ".pdf":
        return _read_pdf(str(file_path))
    if extension in {".html", ".htm"}:
        return _read_html(str(file_path))
    return file_path.read_text(encoding="utf-8", errors="replace")


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


def read_corpus(paths: Iterable[str | Path]) -> list[str]:
    """Read usable corpus files, warning on skipped inputs via stderr.

    A corrupt or unsupported input should not abort a batch with other
    usable files. Each returned text contains at least 51 whitespace tokens.
    """
    texts: list[str] = []
    for path in paths:
        try:
            text = read_file(path)
            if len(text.split()) < MIN_CORPUS_WORDS:
                print(f"  [skip] {path}: fewer than {MIN_CORPUS_WORDS} words", file=sys.stderr)
                continue
            texts.append(text)
        except Exception as exc:
            # Batch ingestion is intentionally best-effort; report failures.
            print(f"  [skip] {path}: {exc}", file=sys.stderr)
    return texts
