"""A portable author profile needs a predictable and safe v1 JSON contract."""
import json

import pytest

from pennovia.voice.analyzer import VoiceProfile


def write_profile(tmp_path, data):
    path = tmp_path / "voice.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_saved_profile_declares_v1_schema(tmp_path):
    path = tmp_path / "profile.json"
    VoiceProfile(author_name="Writer").save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 1
    assert VoiceProfile.load(path).author_name == "Writer"


def test_loads_legacy_unversioned_profile(tmp_path):
    path = write_profile(tmp_path, {"author_name": "Legacy", "avg_sentence_words": 8.5})
    loaded = VoiceProfile.load(path)
    assert loaded.schema_version == 1
    assert loaded.avg_sentence_words == 8.5


def test_ignores_unknown_optional_v1_metadata(tmp_path):
    path = write_profile(tmp_path, {"schema_version": 1, "author_name": "Writer", "extra": {"tag": True}})
    assert VoiceProfile.load(path).author_name == "Writer"


@pytest.mark.parametrize("payload", [[], "text", None, 1])
def test_rejects_non_object_root(tmp_path, payload):
    with pytest.raises(ValueError, match="JSON object"):
        VoiceProfile.load(write_profile(tmp_path, payload))


@pytest.mark.parametrize("version", [2, 0, "1", True])
def test_rejects_unsupported_schema_versions(tmp_path, version):
    with pytest.raises(ValueError, match="schema_version"):
        VoiceProfile.load(write_profile(tmp_path, {"schema_version": version}))


@pytest.mark.parametrize(
    "field,value",
    [
        ("total_words", -1),
        ("text_count", "5"),
        ("avg_sentence_words", float("nan")),
        ("avg_sentence_words", float("inf")),
        ("sentence_std_dev", -1),
        ("first_person_rate", 2),
        ("question_rate", -0.2),
        ("vocabulary_richness", 1.2),
        ("sample_sentences", "not a list"),
        ("sample_sentences", [1, "text"]),
        ("top_transitions", ["but", 1]),
        ("author_name", []),
        ("language", "ru"),
    ],
)
def test_rejects_invalid_known_fields(tmp_path, field, value):
    with pytest.raises(ValueError, match="voice profile|Voice profile"):
        VoiceProfile.load(write_profile(tmp_path, {field: value}))
