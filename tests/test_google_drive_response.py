"""Google Drive exports must reject invalid formats and partial API responses."""
import json
import sys
from types import ModuleType

import pytest

from pennovia.exporter.writer import save_google_drive


def _install_fake_drive(monkeypatch, result):
    google = ModuleType("google")
    google.__path__ = []
    oauth2 = ModuleType("google.oauth2")
    oauth2.__path__ = []
    credentials = ModuleType("google.oauth2.credentials")
    apiclient = ModuleType("googleapiclient")
    apiclient.__path__ = []
    discovery = ModuleType("googleapiclient.discovery")
    http = ModuleType("googleapiclient.http")

    class Credentials:
        @staticmethod
        def from_authorized_user_info(info):
            assert info == {"token": "synthetic"}
            return object()

    class Upload:
        def __init__(self, data, mimetype):
            assert data
            assert mimetype == "text/plain"

    class Service:
        def files(self):
            return self

        def create(self, **kwargs):
            assert kwargs["body"]["mimeType"] == "text/plain"
            assert kwargs["fields"] == "id,webViewLink"
            return self

        def execute(self):
            return result

    credentials.Credentials = Credentials
    discovery.build = lambda *a, **kw: Service()
    http.MediaInMemoryUpload = Upload

    for name, module in {
        "google": google,
        "google.oauth2": oauth2,
        "google.oauth2.credentials": credentials,
        "googleapiclient": apiclient,
        "googleapiclient.discovery": discovery,
        "googleapiclient.http": http,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setenv("GOOGLE_DRIVE_TOKEN", json.dumps({"token": "synthetic"}))


@pytest.mark.parametrize("response,expected", [
    ({"webViewLink": "https://drive.example/file"}, "https://drive.example/file"),
    ({"id": "file123"}, "file123"),
    ({"webViewLink": "", "id": "file123"}, "file123"),
])
def test_drive_accepts_link_or_id_without_eager_fallback(monkeypatch, response, expected):
    _install_fake_drive(monkeypatch, response)
    assert save_google_drive("Draft", "Title", "txt") == expected


@pytest.mark.parametrize("response", [None, [], {}, {"id": None}, {"webViewLink": ""}])
def test_drive_rejects_invalid_upload_response(monkeypatch, response):
    _install_fake_drive(monkeypatch, response)
    with pytest.raises(RuntimeError, match="invalid file response"):
        save_google_drive("Draft", "Title", "txt")


def test_drive_rejects_unsupported_format_before_network(monkeypatch):
    monkeypatch.delenv("GOOGLE_DRIVE_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Unsupported export format"):
        save_google_drive("Draft", "Title", "exe")
