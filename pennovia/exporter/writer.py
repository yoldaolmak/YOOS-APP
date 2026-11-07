"""
Multi-destination, multi-format exporter.
Output: PDF, HTML, TXT
Destinations: local path, Google Drive, WordPress
"""
import os
import re
from html import escape
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path
import tempfile


def _slug(text: str) -> str:
    return re.sub(r"[^\w-]", "-", text.lower())[:60]


def _html_body(content: str, title: str = "") -> str:
    """Escape plain input while supporting simple Markdown headings."""
    blocks = [f"<h1>{escape(title)}</h1>"] if title else []
    for part in content.split("\n\n"):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(#{1,6})\s+([^\n]+)", part)
        if match:
            level = len(match.group(1))
            blocks.append(f"<h{level}>{escape(match.group(2))}</h{level}>")
        else:
            blocks.append(f"<p>{escape(part)}</p>")
    return "\n".join(blocks)


def to_html(content: str, title: str = "") -> str:
    """Create a standalone HTML document from safely escaped text."""
    body = _html_body(content, title)
    return (
        '<!DOCTYPE html>\n<html lang="und">\n<head><meta charset="utf-8">'
        f'<title>{escape(title)}</title>\n'
        '<style>body{max-width:800px;margin:40px auto;font-family:Georgia,serif;'
        'line-height:1.8;color:#222}h1,h2,h3{font-family:sans-serif}</style>\n'
        f'</head>\n<body>{body}</body>\n</html>'
    )


def to_pdf(content: str, title: str = "", output_path: str = None) -> str:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
    except ImportError as exc:
        raise RuntimeError("PDF support requires: pip install reportlab") from exc

    generated_temp = not output_path
    if generated_temp:
        fd, output_path = tempfile.mkstemp(
            prefix=f"pennovia-{_slug(title or 'output')}-", suffix=".pdf"
        )
        os.close(fd)

    try:
        doc = SimpleDocTemplate(output_path, pagesize=A4,
                                leftMargin=2.5*cm, rightMargin=2.5*cm,
                                topMargin=2.5*cm, bottomMargin=2.5*cm)
        styles = getSampleStyleSheet()
        story = []
        if title:
            story.append(Paragraph(escape(title), styles["Title"]))
            story.append(Spacer(1, 0.5*cm))
        for para in content.split("\n\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(escape(para), styles["Normal"]))
                story.append(Spacer(1, 0.3*cm))
        doc.build(story)
        return output_path
    except Exception:
        if generated_temp:
            Path(output_path).unlink(missing_ok=True)
        raise

def save_local(content: str, title: str, fmt: str,
               destination: str = "downloads") -> str:
    """
    destination: "downloads" | "desktop" | absolute path string
    fmt: "html" | "txt" | "pdf". Never replace an existing export.
    """
    if fmt not in {"html", "txt", "pdf"}:
        raise ValueError(f"Unsupported export format: {fmt}")

    home = Path.home()
    dest_map = {
        "downloads": home / "Downloads",
        "desktop": home / "Desktop",
    }
    folder = dest_map.get(destination, Path(destination))
    folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    fd, filepath = tempfile.mkstemp(
        prefix=f"pennovia-{_slug(title)}-{timestamp}-", suffix=f".{fmt}", dir=folder
    )
    os.close(fd)
    try:
        if fmt == "html":
            Path(filepath).write_text(to_html(content, title), encoding="utf-8")
        elif fmt == "pdf":
            to_pdf(content, title, filepath)
        else:
            Path(filepath).write_text(content, encoding="utf-8")
    except Exception:
        Path(filepath).unlink(missing_ok=True)
        raise

    return filepath

def save_google_drive(content: str, title: str, fmt: str) -> str:
    """Upload to Google Drive root folder. Requires GOOGLE_DRIVE_TOKEN env var."""
    if fmt not in {"html", "txt", "pdf"}:
        raise ValueError(f"Unsupported export format: {fmt}")
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaInMemoryUpload
        import json
    except ImportError as exc:
        raise RuntimeError("Google Drive support requires: pip install google-api-python-client google-auth") from exc

    token_json = os.environ.get("GOOGLE_DRIVE_TOKEN")
    if not token_json:
        raise RuntimeError("GOOGLE_DRIVE_TOKEN environment variable not set")

    creds = Credentials.from_authorized_user_info(json.loads(token_json))
    service = build("drive", "v3", credentials=creds)

    mime_types = {"html": "text/html", "txt": "text/plain", "pdf": "application/pdf"}
    mime = mime_types.get(fmt, "text/plain")

    if fmt == "html":
        data = to_html(content, title).encode("utf-8")
    elif fmt == "pdf":
        tmp = to_pdf(content, title)
        try:
            data = Path(tmp).read_bytes()
        finally:
            Path(tmp).unlink(missing_ok=True)
    else:
        data = content.encode("utf-8")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = f"pennovia-{_slug(title)}-{timestamp}.{fmt}"

    file = service.files().create(
        body={"name": name, "mimeType": mime},
        media_body=MediaInMemoryUpload(data, mimetype=mime),
        fields="id,webViewLink",
    ).execute()

    if not isinstance(file, dict):
        raise RuntimeError("Google Drive returned an invalid file response")
    link = file.get("webViewLink") or file.get("id")
    if not isinstance(link, str) or not link.strip():
        raise RuntimeError("Google Drive returned an invalid file response")
    return link


def save_wordpress(content: str, title: str,
                   wp_url: str = None, wp_user: str = None,
                   wp_password: str = None, publish: bool = False) -> str:
    """Publish to WordPress via REST API. Returns post URL."""
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("WordPress support requires: pip install requests") from exc

    url = wp_url or os.environ.get("WP_URL")
    user = wp_user or os.environ.get("WP_USER")
    pwd = wp_password or os.environ.get("WP_APP_PASSWORD")

    if not all([url, user, pwd]):
        raise RuntimeError("Set WP_URL, WP_USER, WP_APP_PASSWORD env vars")

    parsed = urlparse(url)
    if (
        parsed.scheme != "https" or not parsed.hostname
        or parsed.username or parsed.password or parsed.query or parsed.fragment
    ):
        raise ValueError("WordPress export requires a valid HTTPS base URL")
    html_content = _html_body(content)
    status = "publish" if publish else "draft"

    try:
        resp = requests.post(
            f"{url.rstrip('/')}/wp-json/wp/v2/posts",
            auth=(user, pwd),
            json={"title": title, "content": html_content, "status": status},
            verify=True,
            timeout=30,
            allow_redirects=False,
        )
        if 300 <= resp.status_code < 400:
            raise RuntimeError(
                "WordPress redirected the REST request; set WP_URL to its canonical HTTPS URL"
            )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            "WordPress export failed; check HTTPS URL, credentials and connectivity"
        ) from exc

    try:
        result = resp.json()
    except ValueError as exc:
        raise RuntimeError("WordPress returned an invalid post response") from exc
    if not isinstance(result, dict) or not isinstance(result.get("link"), str) or not result["link"].strip():
        raise RuntimeError("WordPress returned an invalid post response")
    return result["link"]
