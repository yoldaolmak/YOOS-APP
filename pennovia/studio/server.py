"""Local-only Studio adapter over the existing Pennovia Python capabilities.

No database, accounts, background jobs or new model API. The browser owns the
draft/profile state; the server supplies bounded source reading and core calls.
"""
import base64
import binascii
import json
import secrets
import tempfile
import threading
import webbrowser
from importlib.resources import files
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from pennovia.content_types.registry import list_types
from pennovia.ingestion.reader import MIN_CORPUS_WORDS, SUPPORTED_EXTENSIONS, read_file, read_url
from pennovia.voice.analyzer import VoiceProfile, analyze
from pennovia.exporter.writer import RemoteOutcomeUnknown


_MAX_REQUEST_BYTES = 12 * 1024 * 1024
_MAX_FILE_BYTES = 4 * 1024 * 1024
_MAX_SOURCES = 20
_BACKENDS = frozenset({"ollama", "openai", "anthropic", "openrouter", "codex"})


def _required_string(payload: dict, field: str, *, limit: int = 300) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{field} must be nonempty and at most {limit} characters")
    return value.strip()


def _collect_sources(items: list) -> tuple[list[str], list[str]]:
    if not isinstance(items, list) or not 1 <= len(items) <= _MAX_SOURCES:
        raise ValueError("Provide between 1 and 20 writing samples")
    texts = []
    warnings = []
    for index, entry in enumerate(items, 1):
        try:
            if not isinstance(entry, dict):
                raise ValueError("Invalid source")
            kind = entry.get("type")
            if kind == "text":
                content = _required_string(entry, "value", limit=1_000_000)
            elif kind == "url":
                content = read_url(_required_string(entry, "value", limit=2048))
            elif kind == "file":
                name = _required_string(entry, "name", limit=255)
                extension = Path(name).suffix.lower()
                if extension not in SUPPORTED_EXTENSIONS:
                    raise ValueError("Choose a TXT, HTML or PDF file")
                encoded = _required_string(entry, "data", limit=6_000_000)
                try:
                    blob = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error) as exc:
                    raise ValueError("Invalid file contents") from exc
                if len(blob) > _MAX_FILE_BYTES:
                    raise ValueError("File exceeds 4 MB")
                with tempfile.TemporaryDirectory(prefix="pennovia-studio-") as folder:
                    source = Path(folder) / f"source{extension}"
                    source.write_bytes(blob)
                    content = read_file(source)
            else:
                raise ValueError("Unsupported sample type")
            if len(content.split()) < MIN_CORPUS_WORDS:
                raise ValueError(f"Fewer than {MIN_CORPUS_WORDS} words")
            texts.append(content)
        except (ValueError, RuntimeError, OSError) as exc:
            warnings.append(f"Sample {index}: {exc}")
    if not texts:
        raise ValueError("No usable writing samples. Provide at least 51 words per sample.")
    return texts, warnings


def _summary(profile: VoiceProfile) -> dict:
    return {
        "profile": json.loads(profile.to_json()),
        "summary": profile.summary(),
    }


def _review(draft: str, profile: VoiceProfile) -> dict:
    from pennovia.audit import audit
    from pennovia.voice.scorer import score

    result = audit(draft, profile)
    return {
        "score": result.total_score,
        "passed": result.passed(),
        "similarity": score(draft, profile),
        "issues": result.issues,
        "details": result.details,
        "components": {
            "Voice": result.voice_match,
            "Transitions": result.transition_match,
            "Structure": result.style_match,
            "No clichés": result.no_ai_cliches,
        },
    }


def _handle_api(path: str, payload: dict) -> dict | tuple[str, bytes, str]:
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    if path == "/api/analyze":
        language = payload.get("language", "auto")
        if language not in ("auto", "en", "tr"):
            raise ValueError("Language must be auto, English or Turkish")
        texts, warnings = _collect_sources(payload.get("sources"))
        profile = analyze(
            texts, author_name=_required_string(payload, "author", limit=120),
            language=language,
        )
        return {**_summary(profile), "accepted": len(texts),
                "words": profile.total_words, "warnings": warnings}
    if path == "/api/profile":
        profile = VoiceProfile.from_dict(payload.get("profile"))
        if profile.total_words == 0 or profile.text_count == 0:
            raise ValueError("Profile has no analyzed writing samples")
        return _summary(profile)
    if path in ("/api/generate", "/api/review", "/api/export"):
        profile = VoiceProfile.from_dict(payload.get("profile"))
        if profile.total_words == 0 or profile.text_count == 0:
            raise ValueError("Profile has no analyzed writing samples")
        if path == "/api/generate":
            from pennovia.voice.generator import generate

            topic = _required_string(payload, "topic", limit=500)
            kind = payload.get("content_type")
            if not isinstance(kind, str) or kind not in list_types():
                raise ValueError("Select a supported writing type")
            backend = payload.get("backend")
            if not isinstance(backend, str) or backend not in _BACKENDS:
                raise ValueError("Select a supported model provider")
            model = payload.get("model", "")
            if not isinstance(model, str) or len(model) > 120:
                raise ValueError("Invalid model name")
            if backend == "codex" and model.strip():
                raise ValueError("Codex CLI does not accept a model override")
            options = {"model": model.strip()} if model.strip() else {}
            draft = generate(profile, kind, topic, backend=backend, **options)
            return {"draft": draft, "review": _review(draft, profile)}
        draft = _required_string(payload, "draft", limit=1_000_000)
        if path == "/api/review":
            return _review(draft, profile)

        from pennovia.exporter.writer import (
            save_google_drive, save_wordpress, to_html, to_pdf,
        )

        destination = payload.get("destination")
        title = _required_string(payload, "title", limit=200)
        if destination == "wordpress":
            return {"url": save_wordpress(draft, title, publish=False),
                    "message": "WordPress draft created"}
        if destination == "google_drive":
            fmt = payload.get("format")
            if fmt not in ("txt", "html", "pdf"):
                raise ValueError("Unsupported download format")
            return {"url": save_google_drive(draft, title, fmt),
                    "message": "Saved to Google Drive"}
        if destination != "download":
            raise ValueError("Unsupported export destination")
        fmt = payload.get("format")
        if fmt == "txt":
            data, mime = draft.encode("utf-8"), "text/plain; charset=utf-8"
        elif fmt == "html":
            data, mime = to_html(draft, title).encode("utf-8"), "text/html; charset=utf-8"
        elif fmt == "pdf":
            path = to_pdf(draft, title)
            try:
                data = Path(path).read_bytes()
            finally:
                Path(path).unlink(missing_ok=True)
            mime = "application/pdf"
        else:
            raise ValueError("Unsupported download format")
        return mime, data, fmt
    raise ValueError("Unknown Studio action")


class _StudioServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int):
        super().__init__(("127.0.0.1", port), _StudioHandler)
        self.studio_token = secrets.token_urlsafe(32)


class _StudioHandler(BaseHTTPRequestHandler):
    server_version = "PennoviaStudio/0.2"

    def log_message(self, format, *args):
        # The browser can contain sensitive author snippets; do not log requests.
        return

    def _headers(self, status: int, content_type: str, size: int,
                 *, filename: str | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()

    def _send(self, status: int, data: bytes, mime: str, *, filename=None):
        self._headers(status, mime, len(data), filename=filename)
        self.wfile.write(data)

    def _json(self, status: int, result: dict):
        self._send(status, json.dumps(result, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _trusted_host(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _trusted_origin(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        return urlsplit(origin).scheme == "http" and urlsplit(origin).netloc in (
            f"127.0.0.1:{self.server.server_address[1]}",
            f"localhost:{self.server.server_address[1]}",
        )

    def do_GET(self):
        if not self._trusted_host():
            self._json(403, {"error": "Untrusted local host"})
            return
        assets = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.css": ("app.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
        }
        asset = assets.get(self.path)
        if asset is None:
            self._json(404, {"error": "Not found"})
            return
        body = files("pennovia.studio").joinpath(asset[0]).read_bytes()
        if self.path == "/":
            body = body.replace(b"__STUDIO_TOKEN__", self.server.studio_token.encode("ascii"))
        self._send(200, body, asset[1])

    def do_POST(self):
        if not self._trusted_host() or not self._trusted_origin():
            self._json(403, {"error": "Cross-origin requests are not allowed"})
            return
        if not secrets.compare_digest(
            self.headers.get("X-Pennovia-Token", ""), self.server.studio_token
        ):
            self._json(403, {"error": "Studio session token required"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._json(415, {"error": "Expected application/json"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= _MAX_REQUEST_BYTES:
                raise ValueError("Request exceeds size limit or is empty")
            data = json.loads(self.rfile.read(length))
            result = _handle_api(self.path, data)
            if isinstance(result, tuple):
                mime, blob, extension = result
                self._send(200, blob, mime, filename=f"pennovia-draft.{extension}")
            else:
                self._json(200, result)
        except RemoteOutcomeUnknown as exc:
            self._json(409, {"error": str(exc), "outcome": "unknown"})
        except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc), "outcome": "failed"})
        except Exception:
            self._json(500, {"error": "Studio could not complete this action"})


def make_server(port: int = 8765) -> ThreadingHTTPServer:
    """Create a loopback-only Studio server; port=0 picks a free test port."""
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535")
    return _StudioServer(port)


def serve(port: int = 8765, *, open_browser: bool = True) -> None:
    with make_server(port) as server:
        address = f"http://127.0.0.1:{server.server_address[1]}"
        print(f"Pennovia Studio: {address}  (Ctrl+C to stop)", flush=True)
        if open_browser:
            threading.Timer(0.2, lambda: webbrowser.open(address)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.shutdown()
