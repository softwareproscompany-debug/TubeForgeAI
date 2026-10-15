"""EDL tests: validation, EDL -> FFmpeg translation, and the API surface."""

import pytest

from projects import edl_to_ffmpeg as e2f
from projects.edl_to_ffmpeg import EDLValidationError, edl_to_ffmpeg, validate_edl


def _clip(clip_id, source, start, in_pt, out_pt, **extra):
    clip = {
        "id": clip_id,
        "source": source,
        "start": start,
        "in": in_pt,
        "out": out_pt,
    }
    clip.update(extra)
    return clip


def _edl(video_clips=(), audio_clips=(), text_clips=(), duration=10.0):
    tracks = [{"id": "v1", "type": "video", "clips": list(video_clips)}]
    if audio_clips:
        tracks.append({"id": "a1", "type": "audio", "clips": list(audio_clips)})
    if text_clips:
        tracks.append({"id": "t1", "type": "text", "clips": list(text_clips)})
    return {"version": 1, "tracks": tracks, "duration": duration}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def test_validate_edl_accepts_minimal_valid_edl():
    edl = _edl(video_clips=[_clip("c1", "a.mp4", 0, 0, 5)])
    assert validate_edl(edl) is True


def test_validate_edl_rejects_wrong_version():
    edl = _edl(video_clips=[_clip("c1", "a.mp4", 0, 0, 5)])
    edl["version"] = 2
    with pytest.raises(EDLValidationError):
        validate_edl(edl)


def test_validate_edl_rejects_unknown_track_type():
    edl = {
        "version": 1,
        "tracks": [{"id": "x", "type": "hologram", "clips": []}],
        "duration": 5,
    }
    with pytest.raises(EDLValidationError):
        validate_edl(edl)


def test_validate_edl_rejects_empty_tracks():
    with pytest.raises(EDLValidationError):
        validate_edl({"version": 1, "tracks": [], "duration": 5})


def test_validate_edl_rejects_out_before_in():
    edl = _edl(video_clips=[_clip("c1", "a.mp4", 0, 4, 2)])
    with pytest.raises(EDLValidationError) as exc:
        validate_edl(edl)
    assert any("out" in d for d in exc.value.details)


def test_validate_edl_rejects_bad_transition():
    edl = _edl(
        video_clips=[
            _clip("c1", "a.mp4", 0, 0, 5, transitions={"out": "morph"})
        ]
    )
    with pytest.raises(EDLValidationError):
        validate_edl(edl)


def test_validate_edl_rejects_overlay_out_of_range():
    edl = _edl(
        text_clips=[
            _clip(
                "t1",
                "overlay",
                0,
                0,
                5,
                textOverlay={
                    "text": "Hi",
                    "x": 1.5,
                    "y": 0.5,
                    "fontSize": 48,
                    "color": "#fff",
                },
            )
        ]
    )
    with pytest.raises(EDLValidationError):
        validate_edl(edl)


def test_is_edl_document_distinguishes_legacy_schema():
    assert e2f.is_edl_document(_edl(video_clips=[_clip("c1", "a.mp4", 0, 0, 5)]))
    legacy = {"version": "v1", "canvas": {}, "video_tracks": []}
    assert not e2f.is_edl_document(legacy)
    assert not e2f.is_edl_document(None)
    assert not e2f.is_edl_document({"version": 1})


# ---------------------------------------------------------------------------
# Translation: single clip
# ---------------------------------------------------------------------------
def test_single_clip_trims_and_outputs_list():
    edl = _edl(video_clips=[_clip("c1", "/media/a.mp4", 0, 2.0, 7.0)])
    cmd = edl_to_ffmpeg(edl, "/out/final.mp4")
    assert isinstance(cmd, list)
    assert cmd[-1] == "/out/final.mp4"
    assert "-i" in cmd and "/media/a.mp4" in cmd
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "trim=start=2.000:end=7.000" in fc
    assert "setpts=PTS-STARTPTS" in fc
    assert "-map" in cmd


def test_single_clip_trims_via_input_index_for_reused_source():
    edl = _edl(
        video_clips=[
            _clip("c1", "a.mp4", 0, 0, 5),
            _clip("c2", "a.mp4", 5, 1, 4),
        ]
    )
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    # One -i per unique source even when reused across clips.
    assert cmd.count("-i") == 1
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "trim=start=0.000:end=5.000" in fc
    assert "trim=start=1.000:end=4.000" in fc


# ---------------------------------------------------------------------------
# Translation: multi-clip concat
# ---------------------------------------------------------------------------
def test_multi_clip_concat_uses_concat_filter():
    edl = _edl(
        video_clips=[
            _clip("c1", "a.mp4", 0, 0, 5),
            _clip("c2", "b.mp4", 5, 0, 3),
        ]
    )
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=0" in fc
    assert "xfade" not in fc


def test_cut_transition_stays_concat():
    edl = _edl(
        video_clips=[
            _clip("c1", "a.mp4", 0, 0, 5, transitions={"out": "cut"}),
            _clip("c2", "b.mp4", 5, 0, 3, transitions={"in": "none"}),
        ]
    )
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "xfade" not in fc


# ---------------------------------------------------------------------------
# Translation: transitions
# ---------------------------------------------------------------------------
def test_dissolve_transition_uses_xfade_crossfade():
    edl = _edl(
        video_clips=[
            _clip("c1", "a.mp4", 0, 0, 5, transitions={"out": "dissolve"}),
            _clip("c2", "b.mp4", 5, 0, 5),
        ]
    )
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "xfade=transition=fade:" in fc  # dissolve == true cross-dissolve
    assert "duration=0.750" in fc
    assert "offset=4.250" in fc  # 5.0 - 0.75


def test_fade_transition_goes_through_black():
    edl = _edl(
        video_clips=[
            _clip("c1", "a.mp4", 0, 0, 5),
            _clip("c2", "b.mp4", 5, 0, 5, transitions={"in": "fade"}),
        ]
    )
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "xfade=transition=fadeblack:" in fc


def test_mixed_transitions_concat_then_xfade():
    edl = _edl(
        video_clips=[
            _clip("c1", "a.mp4", 0, 0, 4),
            _clip("c2", "b.mp4", 4, 0, 4),
            _clip("c3", "c.mp4", 8, 0, 4, transitions={"in": "dissolve"}),
        ]
    )
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=0" in fc
    assert "xfade=transition=fade:" in fc


# ---------------------------------------------------------------------------
# Translation: text overlays + audio
# ---------------------------------------------------------------------------
def test_text_overlay_uses_drawtext_with_timing():
    edl = _edl(
        video_clips=[_clip("c1", "a.mp4", 0, 0, 10)],
        text_clips=[
            _clip(
                "t1",
                "overlay",
                2,
                0,
                6,
                textOverlay={
                    "text": "Hello: world",
                    "x": 0.5,
                    "y": 0.85,
                    "fontSize": 48,
                    "color": "#ffffff",
                },
            )
        ],
    )
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "drawtext=" in fc
    assert "Hello\\: world" in fc  # colon escaped for the filter parser
    assert "fontsize=48" in fc
    assert "fontcolor=#ffffff" in fc
    assert "between(t,2.000,8.000)" in fc  # start=2, window = out-in = 6


def test_audio_clips_are_delayed_and_mixed():
    edl = _edl(
        video_clips=[_clip("c1", "a.mp4", 0, 0, 10)],
        audio_clips=[
            _clip("au1", "narr.mp3", 1.5, 0, 5),
            _clip("au2", "music.mp3", 0, 10, 20),
        ],
    )
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "atrim=start=0.000:end=5.000" in fc
    assert "adelay=1500|1500" in fc
    assert "amix=inputs=2" in fc
    assert "-an" not in cmd


def test_no_audio_disables_audio_stream():
    edl = _edl(video_clips=[_clip("c1", "a.mp4", 0, 0, 5)])
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    assert "-an" in cmd


def test_audio_only_edl_synthesizes_black_canvas():
    edl = _edl(audio_clips=[_clip("au1", "narr.mp3", 0, 0, 5)], duration=5.0)
    cmd = edl_to_ffmpeg(edl, "/out.mp4")
    assert "-f" in cmd and "lavfi" in cmd
    joined = " ".join(cmd)
    assert "color=c=black" in joined


def test_encoding_settings_are_honored():
    edl = _edl(video_clips=[_clip("c1", "a.mp4", 0, 0, 5)])
    cmd = edl_to_ffmpeg(
        edl,
        "/out.mp4",
        {"video_codec": "libx265", "crf": 23, "width": 1280, "height": 720},
    )
    assert "libx265" in cmd
    assert "23" in cmd
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "scale=1280:720" in fc


def test_invalid_edl_raises_from_translator():
    with pytest.raises(EDLValidationError):
        edl_to_ffmpeg({"version": 1, "tracks": [], "duration": 1}, "/out.mp4")


# ---------------------------------------------------------------------------
# API: timeline save + render queue
# ---------------------------------------------------------------------------
def _auth_edl(auth_client, project, edl_body):
    return auth_client.post(
        f"/api/v1/projects/{project.id}/timeline", edl_body, format="json"
    )


def test_timeline_endpoint_accepts_edl(auth_client, project):
    edl = _edl(video_clips=[_clip("c1", "a.mp4", 0, 0, 5)])
    res = _auth_edl(auth_client, project, {"edl": edl})
    assert res.status_code == 201, res.content
    assert res.data["timeline_json"] == edl
    assert res.data["version_number"] == 1


def test_timeline_endpoint_accepts_bare_edl_document(auth_client, project):
    edl = _edl(video_clips=[_clip("c1", "a.mp4", 0, 0, 5)])
    res = _auth_edl(auth_client, project, edl)
    assert res.status_code == 201, res.content


def test_timeline_endpoint_rejects_invalid_edl(auth_client, project):
    res = _auth_edl(auth_client, project, {"edl": {"version": 1, "tracks": []}})
    assert res.status_code == 400


def test_timeline_endpoint_still_accepts_legacy_schema(auth_client, project):
    legacy = {
        "version": "v1",
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "video_tracks": [],
        "audio_tracks": [],
    }
    res = _auth_edl(auth_client, project, {"timeline_json": legacy})
    assert res.status_code == 201, res.content


def test_render_endpoint_queues_edl_job(auth_client, project):
    edl = _edl(video_clips=[_clip("c1", "a.mp4", 0, 0, 5)])
    saved = _auth_edl(auth_client, project, {"edl": edl})
    version_id = saved.data["id"]
    res = auth_client.post(
        f"/api/v1/projects/{project.id}/timeline/{version_id}/render", {}, format="json"
    )
    assert res.status_code == 201, res.content
    assert res.data["status"] == "QUEUED"
    assert str(res.data["timeline_version"]) == version_id
    manifest = res.data["manifest"]
    assert manifest["edl"] is True
    assert manifest["ffmpeg_command"][-1].endswith(".mp4")


def test_render_endpoint_rejects_non_edl_version(auth_client, project):
    legacy = {
        "version": "v1",
        "canvas": {"width": 1920, "height": 1080, "fps": 30},
        "video_tracks": [],
        "audio_tracks": [],
    }
    saved = _auth_edl(auth_client, project, {"timeline_json": legacy})
    version_id = saved.data["id"]
    res = auth_client.post(
        f"/api/v1/projects/{project.id}/timeline/{version_id}/render", {}, format="json"
    )
    assert res.status_code == 400


def test_render_endpoint_rejects_other_users_project(auth_client2, project):
    edl = _edl(video_clips=[_clip("c1", "a.mp4", 0, 0, 5)])
    res = auth_client2.post(
        f"/api/v1/projects/{project.id}/timeline", {"edl": edl}, format="json"
    )
    assert res.status_code == 404
