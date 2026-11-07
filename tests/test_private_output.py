"""Private author-derived outputs must be safe across failures and retries."""
import os
import stat

import pytest

from pennovia import storage
from pennovia.voice.analyzer import VoiceProfile


def test_new_profile_and_draft_are_private_on_posix(tmp_path):
    profile = tmp_path / "voice.json"
    draft = tmp_path / "draft.txt"
    VoiceProfile(author_name="Example").save(profile, overwrite=False)
    storage.write_private_text(draft, "Private generated text")
    if os.name == "posix":
        assert stat.S_IMODE(profile.stat().st_mode) == 0o600
        assert stat.S_IMODE(draft.stat().st_mode) == 0o600


def test_existing_output_rejected_without_modification(tmp_path):
    target = tmp_path / "draft.txt"
    storage.write_private_text(target, "First")
    with pytest.raises(FileExistsError):
        storage.write_private_text(target, "Second")
    assert target.read_text(encoding="utf-8") == "First"


def test_explicit_overwrite_replaces_content_without_leftover_temp(tmp_path):
    target = tmp_path / "voice.json"
    storage.write_private_text(target, "First")
    storage.write_private_text(target, "Second", overwrite=True)
    assert target.read_text(encoding="utf-8") == "Second"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["voice.json"]
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_failed_atomic_replace_leaves_existing_file_intact(tmp_path, monkeypatch):
    target = tmp_path / "profile.json"
    target.write_text("important original", encoding="utf-8")

    def reject_replace(*args, **kwargs):
        raise OSError("simulated interrupted replacement")

    monkeypatch.setattr(storage.os, "replace", reject_replace)
    with pytest.raises(OSError, match="simulated"):
        storage.write_private_text(target, "new profile", overwrite=True)
    assert target.read_text(encoding="utf-8") == "important original"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["profile.json"]


def test_invalid_profile_serialization_cannot_truncate_existing_file(tmp_path):
    target = tmp_path / "profile.json"
    target.write_text("important original", encoding="utf-8")
    broken = VoiceProfile(sample_sentences=[object()])
    with pytest.raises(TypeError):
        broken.save(target)
    assert target.read_text(encoding="utf-8") == "important original"


def test_atomic_replacement_does_not_follow_existing_symlink(tmp_path):
    if os.name != "posix":
        pytest.skip("symlink behavior is POSIX-specific")
    secret = tmp_path / "secret.txt"
    secret.write_text("do not touch", encoding="utf-8")
    link = tmp_path / "profile.json"
    link.symlink_to(secret)
    storage.write_private_text(link, "new content", overwrite=True)
    assert secret.read_text(encoding="utf-8") == "do not touch"
    assert not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "new content"
