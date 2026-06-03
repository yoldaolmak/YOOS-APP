"""
API integration tests — uses FastAPI TestClient, no real HTTP server.
No API keys required; generation tests use a mock backend.
"""
from __future__ import annotations
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from graphova.app import app
from graphova.api.routes import set_db
from graphova.api.db import ProfileDB

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "corpus")

_TWAIN_PATHS = [
    os.path.join(CORPUS_DIR, f)
    for f in ["twain_01.txt", "twain_02.txt", "twain_03.txt"]
    if os.path.exists(os.path.join(CORPUS_DIR, f))
]
_HAS_TWAIN = len(_TWAIN_PATHS) > 0


@pytest.fixture
def client(tmp_path):
    """TestClient with an isolated temp database."""
    db = ProfileDB(tmp_path / "test.db")
    set_db(db)
    with TestClient(app) as c:
        yield c
    set_db(None)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "profiles_count" in data
    assert isinstance(data["available_backends"], list)
    assert isinstance(data["llm_ready"], bool)


# ── Genres ────────────────────────────────────────────────────────────────────

def test_get_genres(client):
    r = client.get("/api/genres")
    assert r.status_code == 200
    genres = r.json()
    assert "travel_blog" in genres
    assert len(genres) >= 6


# ── Profile list (empty) ──────────────────────────────────────────────────────

def test_list_profiles_empty(client):
    r = client.get("/api/profiles")
    assert r.status_code == 200
    assert r.json() == []


# ── Create profile ────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _HAS_TWAIN, reason="Twain corpus not available")
def test_create_profile(client):
    files = [("files", (os.path.basename(p), open(p, "rb"), "text/plain"))
             for p in _TWAIN_PATHS]
    data = {"name": "Test Twain", "author": "Mark Twain"}
    r = client.post("/api/profiles", files=files, data=data)
    assert r.status_code == 201
    body = r.json()
    assert "id" in body
    assert body["name"] == "Test Twain"
    assert body["corpus_words"] > 0
    assert body["language"] in ("en", "tr")
    assert "summary" in body


@pytest.mark.skipif(not _HAS_TWAIN, reason="Twain corpus not available")
def test_create_profile_shows_in_list(client):
    files = [("files", (os.path.basename(p), open(p, "rb"), "text/plain"))
             for p in _TWAIN_PATHS]
    client.post("/api/profiles", files=files, data={"name": "List Test"})
    r = client.get("/api/profiles")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "List Test" in names


def test_create_profile_no_files(client):
    r = client.post("/api/profiles", files=[], data={"name": "Empty"})
    assert r.status_code in (400, 422)


def test_create_profile_unsupported_extension(client):
    files = [("files", ("data.csv", b"a,b,c,d" * 100, "text/csv"))]
    r = client.post("/api/profiles", files=files, data={"name": "Bad Type"})
    assert r.status_code == 400


def test_create_profile_all_short_files(client):
    """All files < 50 words should return 422."""
    files = [("files", ("short.txt", b"Too short.", "text/plain"))]
    r = client.post("/api/profiles", files=files, data={"name": "Short"})
    assert r.status_code == 422


def test_create_profile_file_too_large(client):
    large_data = b"word " * (10 * 1024 * 1024 + 100)  # > 10MB
    files = [("files", ("big.txt", large_data, "text/plain"))]
    r = client.post("/api/profiles", files=files, data={"name": "Big"})
    assert r.status_code == 400


# ── Get / delete profile ──────────────────────────────────────────────────────

@pytest.mark.skipif(not _HAS_TWAIN, reason="Twain corpus not available")
def test_get_profile_detail(client):
    files = [("files", (os.path.basename(p), open(p, "rb"), "text/plain"))
             for p in _TWAIN_PATHS]
    created = client.post("/api/profiles", files=files, data={"name": "Detail Test"})
    pid = created.json()["id"]

    r = client.get(f"/api/profiles/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == pid
    assert "fingerprint" in body
    fp = body["fingerprint"]
    assert "avg_sentence_words" in fp
    assert "top_transitions" in fp


def test_get_profile_not_found(client):
    r = client.get("/api/profiles/nonexistent-id")
    assert r.status_code == 404


@pytest.mark.skipif(not _HAS_TWAIN, reason="Twain corpus not available")
def test_delete_profile(client):
    files = [("files", (os.path.basename(p), open(p, "rb"), "text/plain"))
             for p in _TWAIN_PATHS]
    created = client.post("/api/profiles", files=files, data={"name": "Delete Test"})
    pid = created.json()["id"]

    r = client.delete(f"/api/profiles/{pid}")
    assert r.status_code == 200

    r2 = client.get(f"/api/profiles/{pid}")
    assert r2.status_code == 404


def test_delete_profile_not_found(client):
    r = client.delete("/api/profiles/does-not-exist")
    assert r.status_code == 404


# ── Search ────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _HAS_TWAIN, reason="Twain corpus not available")
def test_search_profiles(client):
    files = [("files", (os.path.basename(p), open(p, "rb"), "text/plain"))
             for p in _TWAIN_PATHS]
    client.post("/api/profiles", files=files,
                data={"name": "Searchable Twain", "author": "Mark Twain"})

    r = client.get("/api/profiles?q=Twain")
    assert r.status_code == 200
    results = r.json()
    assert len(results) >= 1

    r2 = client.get("/api/profiles?q=xyz_no_match")
    assert r2.json() == []


# ── Generate — mock backend ───────────────────────────────────────────────────

@pytest.mark.skipif(not _HAS_TWAIN, reason="Twain corpus not available")
def test_generate_unknown_profile(client):
    r = client.post("/api/generate", json={
        "profile_id": "does-not-exist",
        "topic": "Paris",
        "genre": "travel_blog",
        "backend": "auto",
    })
    assert r.status_code == 404


@pytest.mark.skipif(not _HAS_TWAIN, reason="Twain corpus not available")
def test_generate_invalid_genre(client):
    files = [("files", (os.path.basename(p), open(p, "rb"), "text/plain"))
             for p in _TWAIN_PATHS]
    created = client.post("/api/profiles", files=files, data={"name": "Genre Test"})
    pid = created.json()["id"]

    r = client.post("/api/generate", json={
        "profile_id": pid,
        "topic": "Test",
        "genre": "invalid_genre_xyz",
        "backend": "auto",
    })
    assert r.status_code == 422


@pytest.mark.skipif(not _HAS_TWAIN, reason="Twain corpus not available")
def test_generate_invalid_backend(client):
    files = [("files", (os.path.basename(p), open(p, "rb"), "text/plain"))
             for p in _TWAIN_PATHS]
    created = client.post("/api/profiles", files=files, data={"name": "Backend Test"})
    pid = created.json()["id"]

    r = client.post("/api/generate", json={
        "profile_id": pid,
        "topic": "Test",
        "genre": "travel_blog",
        "backend": "fake_backend",
    })
    assert r.status_code == 422


# ── Export ────────────────────────────────────────────────────────────────────

def test_export_txt(client):
    r = client.post("/api/export", json={
        "content": "This is a test. " * 10,
        "title": "Test Export",
        "format": "txt",
    })
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")

def test_export_html(client):
    r = client.post("/api/export", json={
        "content": "This is a test. " * 10,
        "title": "HTML Export",
        "format": "html",
    })
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")

def test_export_invalid_format(client):
    r = client.post("/api/export", json={
        "content": "Content here.",
        "title": "Bad Format",
        "format": "docx",
    })
    assert r.status_code == 422

def test_export_empty_content(client):
    r = client.post("/api/export", json={
        "content": "",
        "title": "Empty",
        "format": "txt",
    })
    assert r.status_code == 422


# ── Database ──────────────────────────────────────────────────────────────────

def test_db_create_get_delete():
    from graphova.core.fingerprint import VoiceFingerprint
    with tempfile.TemporaryDirectory() as d:
        db = ProfileDB(os.path.join(d, "test.db"))
        fp = VoiceFingerprint(author_name="DB Test", avg_sentence_words=12.0,
                              total_words=5000)
        pid = db.create("My Profile", fp, corpus_files=3)
        assert pid

        row = db.get(pid)
        assert row is not None
        assert row["name"] == "My Profile"
        assert row["fingerprint"].author_name == "DB Test"
        assert row["corpus_files"] == 3

        all_profiles = db.list_all()
        assert len(all_profiles) == 1
        assert all_profiles[0]["name"] == "My Profile"

        assert db.count() == 1

        result = db.delete(pid)
        assert result is True
        assert db.get(pid) is None
        assert db.count() == 0

def test_db_delete_nonexistent():
    with tempfile.TemporaryDirectory() as d:
        db = ProfileDB(os.path.join(d, "test.db"))
        assert db.delete("nonexistent-id") is False

def test_db_search():
    from graphova.core.fingerprint import VoiceFingerprint
    with tempfile.TemporaryDirectory() as d:
        db = ProfileDB(os.path.join(d, "test.db"))
        fp = VoiceFingerprint(author_name="Hemingway")
        db.create("Hemingway Study", fp)
        db.create("Other Profile", VoiceFingerprint(author_name="Other"))

        results = db.search("hemingway")
        assert len(results) == 1
        assert results[0]["name"] == "Hemingway Study"

        empty = db.search("xyz_no_match")
        assert empty == []
