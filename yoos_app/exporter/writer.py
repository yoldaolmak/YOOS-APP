"""
Multi-destination, multi-format exporter.
Output: PDF, HTML, TXT
Destinations: local path, Google Drive, WordPress
"""
import os
import re
from datetime import datetime
from pathlib import Path


def _slug(text: str) -> str:
    return re.sub(r"[^\w-]", "-", text.lower())[:60]


def to_html(content: str, title: str = "") -> str:
    paragraphs = content.split("\n\n")
    body = ""
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith("#"):
            level = len(p) - len(p.lstrip("#"))
            text = p.lstrip("# ").strip()
            body += f"<h{level}>{text}</h{level}>\n"
        else:
            body += f"<p>{p}</p>\n"
    return f"""<!DOCTYPE html>
<html lang="tr">
<head><meta charset="utf-8"><title>{title}</title>
<style>body{{max-width:800px;margin:40px auto;font-family:Georgia,serif;line-height:1.8;color:#222}}h1,h2,h3{{font-family:sans-serif}}p{{margin:1em 0}}</style>
</head>
<body>{"<h1>"+title+"</h1>" if title else ""}{body}</body>
</html>"""


def to_pdf(content: str, title: str = "", output_path: str = None) -> str:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
    except ImportError:
        raise RuntimeError("PDF support requires: pip install reportlab")

    if not output_path:
        output_path = f"/tmp/yoos-{_slug(title or 'output')}.pdf"

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2.5*cm, rightMargin=2.5*cm,
                            topMargin=2.5*cm, bottomMargin=2.5*cm)
    styles = getSampleStyleSheet()
    story = []
    if title:
        story.append(Paragraph(title, styles["Title"]))
        story.append(Spacer(1, 0.5*cm))
    for para in content.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para, styles["Normal"]))
            story.append(Spacer(1, 0.3*cm))
    doc.build(story)
    return output_path


def save_local(content: str, title: str, fmt: str,
               destination: str = "downloads") -> str:
    """
    destination: "downloads" | "desktop" | absolute path string
    fmt: "html" | "txt" | "pdf"
    """
    home = Path.home()
    dest_map = {
        "downloads": home / "Downloads",
        "desktop": home / "Desktop",
    }
    folder = dest_map.get(destination, Path(destination))
    folder.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    filename = f"yoos-{_slug(title)}-{timestamp}.{fmt}"
    filepath = str(folder / filename)

    if fmt == "html":
        (folder / filename).write_text(to_html(content, title), encoding="utf-8")
    elif fmt == "pdf":
        to_pdf(content, title, filepath)
    else:
        (folder / filename).write_text(content, encoding="utf-8")

    return filepath


def save_google_drive(content: str, title: str, fmt: str) -> str:
    """Upload to Google Drive root folder. Requires GOOGLE_DRIVE_TOKEN env var."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaInMemoryUpload
        import json
    except ImportError:
        raise RuntimeError("Google Drive support requires: pip install google-api-python-client google-auth")

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
        data = open(tmp, "rb").read()
    else:
        data = content.encode("utf-8")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    name = f"yoos-{_slug(title)}-{timestamp}.{fmt}"

    file = service.files().create(
        body={"name": name, "mimeType": mime},
        media_body=MediaInMemoryUpload(data, mimetype=mime),
        fields="id,webViewLink",
    ).execute()

    return file.get("webViewLink", file["id"])


def save_wordpress(content: str, title: str,
                   wp_url: str = None, wp_user: str = None,
                   wp_password: str = None, publish: bool = False) -> str:
    """Publish to WordPress via REST API. Returns post URL."""
    try:
        import requests
    except ImportError:
        raise RuntimeError("WordPress support requires: pip install requests")

    url = wp_url or os.environ.get("WP_URL")
    user = wp_user or os.environ.get("WP_USER")
    pwd = wp_password or os.environ.get("WP_APP_PASSWORD")

    if not all([url, user, pwd]):
        raise RuntimeError("Set WP_URL, WP_USER, WP_APP_PASSWORD env vars")

    html_content = to_html(content, title)
    status = "publish" if publish else "draft"

    resp = requests.post(
        f"{url.rstrip('/')}/wp-json/wp/v2/posts",
        auth=(user, pwd),
        json={"title": title, "content": html_content, "status": status},
        verify=False,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("link", "")
