"""Media engine tests: timeline validation, incremental planning, render manifests."""
import pytest

from projects import media_engine
from projects.media_engine import TimelineValidationError


def _valid_timeline():
    return {
        "version": "v1",
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "video_tracks": [
            {"id": "v1", "clips": [
                {"id": "c1", "asset_id": "a1", "scene_id": "s1",
                 "start": 0, "duration": 5, "in_point": 0, "out_point": 5,
                 "transition": {"type": "fade", "duration": 0.5}},
                {"id": "c2", "asset_id": "a2", "scene_id": "s2",
                 "start": 5, "duration": 5, "in_point": 0, "out_point": 5},
            ]},
        ],
        "audio_tracks": [
            {"id": "a-t1", "kind": "narration", "clips": [
                {"id": "ac1", "asset_id": "a3", "start": 0, "duration": 10,
                 "gain_db": 0, "fade_in": 0.5, "fade_out": 0.5},
            ]},
        ],
        "captions": [{"start": 0, "end": 4, "text": "Hello world"}],
        "overlays": [],
    }


def test_validate_timeline_accepts_valid():
    assert media_engine.validate_timeline(_valid_timeline()) is True


def test_validate_timeline_rejects_invalid():
    bad = {"version": "v1"}  # missing canvas
    with pytest.raises(TimelineValidationError) as exc_info:
        media_engine.validate_timeline(bad)
    assert exc_info.value.details

    bad_transition = _valid_timeline()
    bad_transition["video_tracks"][0]["clips"][0]["transition"] = {"type": "explode"}
    with pytest.raises(TimelineValidationError):
        media_engine.validate_timeline(bad_transition)


def test_incremental_plan_reuses_unchanged_scenes():
    old = _valid_timeline()
    new = _valid_timeline()
    new["video_tracks"][0]["clips"][0]["duration"] = 7  # scene s1 changed
    plan = media_engine.compute_incremental_plan(old, new)
    assert plan["changed_scenes"] == ["s1"]
    assert "a2" in plan["reusable_assets"]  # untouched clip keeps its asset
    assert "a1" not in plan["reusable_assets"]
    assert "assemble_video" in plan["stages_to_rerun"]
    assert "encode" in plan["stages_to_rerun"]


def test_incremental_plan_no_changes_reruns_nothing():
    timeline = _valid_timeline()
    plan = media_engine.compute_incremental_plan(timeline, _valid_timeline())
    assert plan["changed_scenes"] == []
    assert plan["stages_to_rerun"] == []
    assert set(plan["reusable_assets"]) == {"a1", "a2"}


def test_build_render_manifest_contains_hashes_and_versions():
    manifest = media_engine.build_render_manifest(
        {"a1": "abc123", "a2": "def456"}, "tv-1",
        {"video_codec": "libx264"}, {"timeline_valid": True},
    )
    assert manifest["asset_hashes"] == {"a1": "abc123", "a2": "def456"}
    assert manifest["timeline_version_id"] == "tv-1"
    assert manifest["manifest_version"] == "v1"
    assert "renderer_version" in manifest  # pinned from `ffmpeg -version`
    assert manifest["validation"] == {"timeline_valid": True}
