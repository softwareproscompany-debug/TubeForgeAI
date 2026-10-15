"""EDL (Edit Decision List) validation + translation to an FFmpeg command.

The EDL is the interchange format produced by the in-app video editor
(``frontend/lib/edl.ts``)::

    {
        "version": 1,
        "tracks": [
            {"id": "v1", "type": "video", "clips": [
                {"id": "c1", "source": "https://…/a.mp4",
                 "start": 0.0, "in": 2.0, "out": 7.0,
                 "transitions": {"out": "dissolve"},
                 "textOverlay": {"text": "Hello", "x": 0.5, "y": 0.85,
                                 "fontSize": 48, "color": "#ffffff"}}
            ]},
            {"id": "a1", "type": "audio", "clips": [...]},
            {"id": "t1", "type": "text",  "clips": [...]}
        ],
        "duration": 12.5
    }

Semantics:

* ``clip.start`` — position on the timeline in seconds.
* ``clip.in`` / ``clip.out`` — trim points *within the source media* in seconds;
  the clip's timeline duration is ``out - in``.
* ``transitions.in`` / ``transitions.out`` — one of
  ``none`` | ``cut`` | ``fade`` | ``dissolve``, applied at the clip's head/tail
  boundary. ``fade`` is rendered as an xfade *through black* (``fadeblack``);
  ``dissolve`` is rendered as a true cross-dissolve (xfade ``fade``).
* ``textOverlay.x`` / ``y`` — fractional position (0..1) of the text anchor.
* All times are in seconds.

``edl_to_ffmpeg`` only *builds* the command (a list of argv strings); it never
executes it. Execution is the render worker's job
(``projects.media_engine.RenderWorker``).
"""

import shutil

EDL_VERSION = 1
TRACK_TYPES = ("video", "audio", "text")
TRANSITION_TYPES = ("none", "cut", "fade", "dissolve")
# Cross-dissolve length in seconds for fade/dissolve boundaries.
TRANSITION_DURATION = 0.75


class EDLValidationError(Exception):
    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or []


def _err(details, message):
    details.append(message)


def _is_num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_edl(data):
    """Validate an EDL dict. Returns True; raises EDLValidationError on failure."""
    details = []
    if not isinstance(data, dict):
        raise EDLValidationError("EDL must be a JSON object.", ["not_an_object"])
    if data.get("version") != EDL_VERSION:
        _err(details, f"edl.version must be {EDL_VERSION}")
    tracks = data.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        _err(details, "edl.tracks must be a non-empty list")
        tracks = []
    total_clips = 0
    for track in tracks:
        if not isinstance(track, dict):
            _err(details, "each track must be an object")
            continue
        track_id = track.get("id", "?")
        if not track.get("id"):
            _err(details, "each track must have an id")
        if track.get("type") not in TRACK_TYPES:
            _err(details, f"track {track_id!r}: type must be one of {TRACK_TYPES}")
        clips = track.get("clips")
        if not isinstance(clips, list):
            _err(details, f"track {track_id!r}: clips must be a list")
            continue
        for clip in clips:
            total_clips += 1
            _validate_clip(clip, track_id, details)
    if total_clips == 0:
        _err(details, "edl must contain at least one clip")
    duration = data.get("duration")
    if not _is_num(duration) or duration <= 0:
        _err(details, "edl.duration must be a positive number")
    if details:
        raise EDLValidationError("EDL failed validation.", details)
    return True


def _validate_clip(clip, track_id, details):
    if not isinstance(clip, dict):
        _err(details, f"track {track_id!r}: each clip must be an object")
        return
    clip_id = clip.get("id", "?")
    ctx = f"track {track_id!r} clip {clip_id!r}"
    if not clip.get("id"):
        _err(details, f"{ctx}: missing id")
    if not isinstance(clip.get("source"), str) or not clip["source"].strip():
        _err(details, f"{ctx}: source must be a non-empty string")
    for key in ("start", "in", "out"):
        if not _is_num(clip.get(key)):
            _err(details, f"{ctx}: {key} must be a number")
    if _is_num(clip.get("start")) and clip["start"] < 0:
        _err(details, f"{ctx}: start must be >= 0")
    if _is_num(clip.get("in")) and clip["in"] < 0:
        _err(details, f"{ctx}: in must be >= 0")
    if (
        _is_num(clip.get("in"))
        and _is_num(clip.get("out"))
        and clip["out"] <= clip["in"]
    ):
        _err(details, f"{ctx}: out must be greater than in")
    transitions = clip.get("transitions") or {}
    if not isinstance(transitions, dict):
        _err(details, f"{ctx}: transitions must be an object")
    else:
        for edge in ("in", "out"):
            value = transitions.get(edge)
            if value is not None and value not in TRANSITION_TYPES:
                _err(details, f"{ctx}: transitions.{edge} must be one of {TRANSITION_TYPES}")
    overlay = clip.get("textOverlay")
    if overlay is not None:
        if not isinstance(overlay, dict):
            _err(details, f"{ctx}: textOverlay must be an object")
        else:
            if not isinstance(overlay.get("text"), str):
                _err(details, f"{ctx}: textOverlay.text must be a string")
            for axis in ("x", "y"):
                value = overlay.get(axis)
                if not _is_num(value) or not 0 <= value <= 1:
                    _err(details, f"{ctx}: textOverlay.{axis} must be between 0 and 1")
            if not _is_num(overlay.get("fontSize")) or overlay["fontSize"] <= 0:
                _err(details, f"{ctx}: textOverlay.fontSize must be a positive number")
            if not isinstance(overlay.get("color"), str) or not overlay["color"]:
                _err(details, f"{ctx}: textOverlay.color must be a non-empty string")


def is_edl_document(data):
    """Heuristic: is this timeline_json an EDL document (vs the legacy v1 schema)?

    The legacy schema uses ``{"version": "v1", "video_tracks": [...]}`` while the
    EDL uses ``{"version": 1, "tracks": [{"type": "video"|"audio"|"text", …}]}``.
    """
    if not isinstance(data, dict):
        return False
    if data.get("version") != EDL_VERSION:
        return False
    tracks = data.get("tracks")
    if not isinstance(tracks, list):
        return False
    return all(
        isinstance(t, dict) and t.get("type") in TRACK_TYPES for t in tracks
    )


def _fmt(value):
    return f"{float(value):.3f}"


def _escape_drawtext(text):
    """Escape text for the drawtext filter argument."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("\n", " ")
    )


def _video_clips(edl):
    clips = [
        clip
        for track in edl["tracks"]
        if track["type"] == "video"
        for clip in track["clips"]
    ]
    return sorted(clips, key=lambda c: (c["start"], c["id"]))


def _audio_clips(edl):
    clips = [
        clip
        for track in edl["tracks"]
        if track["type"] == "audio"
        for clip in track["clips"]
    ]
    return sorted(clips, key=lambda c: (c["start"], c["id"]))


def _text_overlays(edl):
    """(clip, overlay, timeline_start, timeline_end) for every text overlay."""
    found = []
    for track in edl["tracks"]:
        for clip in track["clips"]:
            overlay = clip.get("textOverlay")
            if overlay:
                end = clip["start"] + (clip["out"] - clip["in"])
                found.append((overlay, clip["start"], end))
    # Text-track clips carry the overlay timing; a text track's own in/out
    # doubles as the overlay window.
    return sorted(found, key=lambda item: item[1])


def edl_to_ffmpeg(edl, output_path, encoding_settings=None):
    """Translate an EDL into an FFmpeg command (list of argv strings).

    Raises EDLValidationError if the EDL is invalid. Never executes anything.
    """
    validate_edl(edl)
    settings = encoding_settings or {}
    width = int(settings.get("width", 1920))
    height = int(settings.get("height", 1080))
    fps = int(settings.get("fps", 30))

    video_clips = _video_clips(edl)
    audio_clips = _audio_clips(edl)

    # -- inputs: one -i per unique source, in first-use order ------------------
    sources = []
    for clip in video_clips + audio_clips:
        if clip["source"] not in sources:
            sources.append(clip["source"])
    input_index = {src: i for i, src in enumerate(sources)}

    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-y"]
    if not video_clips:
        # Audio/text-only EDL: synthesize a black canvas for the full duration.
        cmd += [
            "-f", "lavfi", "-i",
            f"color=c=black:s={width}x{height}:r={fps}:d={_fmt(edl['duration'])}",
        ]
        synth_video_input = 0
    for src in sources:
        cmd += ["-i", src]

    parts = []

    # -- video: trim each clip, normalize, then concat / xfade ----------------
    def boundary_transition(left, right):
        out_t = (left.get("transitions") or {}).get("out")
        in_t = (right.get("transitions") or {}).get("in")
        for candidate in (out_t, in_t):
            if candidate and candidate not in ("none", "cut"):
                return candidate
        return None

    if video_clips:
        seg_labels = []
        for i, clip in enumerate(video_clips):
            src_idx = input_index[clip["source"]]
            parts.append(
                f"[{src_idx}:v]"
                f"trim=start={_fmt(clip['in'])}:end={_fmt(clip['out'])},"
                f"setpts=PTS-STARTPTS,"
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                f"fps={fps},format=yuv420p[v{i}]"
            )
            seg_labels.append((f"[v{i}]", clip["out"] - clip["in"]))

        # Group consecutive clips into runs separated by xfade boundaries.
        runs = [[0]]
        run_transitions = []  # transition between run r and run r+1
        for i in range(1, len(video_clips)):
            t = boundary_transition(video_clips[i - 1], video_clips[i])
            if t in ("fade", "dissolve"):
                runs.append([i])
                run_transitions.append(t)
            else:
                runs[-1].append(i)

        run_labels = []
        for r, run in enumerate(runs):
            if len(run) == 1:
                label, dur = seg_labels[run[0]]
                run_labels.append((label, dur))
            else:
                joined = "".join(label for label, _ in (seg_labels[i] for i in run))
                dur = sum(d for _, d in (seg_labels[i] for i in run))
                parts.append(f"{joined}concat=n={len(run)}:v=1:a=0[run{r}]")
                run_labels.append((f"[run{r}]", dur))

        cur_label, cur_dur = run_labels[0]
        for r in range(1, len(run_labels)):
            t = run_transitions[r - 1]
            run_label, run_dur = run_labels[r]
            d = min(TRANSITION_DURATION, cur_dur / 2, run_dur / 2)
            d = max(d, 0.05)
            offset = max(cur_dur - d, 0)
            xf = "fadeblack" if t == "fade" else "fade"
            parts.append(
                f"{cur_label}{run_label}"
                f"xfade=transition={xf}:duration={_fmt(d)}:offset={_fmt(offset)}"
                f"[xf{r}]"
            )
            cur_label, cur_dur = f"[xf{r}]", cur_dur + run_dur - d
        vlabel = cur_label
    else:
        vlabel = f"[{synth_video_input}:v]"
        parts.append(
            f"{vlabel}scale={width}:{height},fps={fps},format=yuv420p[vbase]"
        )
        vlabel = "[vbase]"

    # -- text overlays via drawtext -------------------------------------------
    for k, (overlay, t_start, t_end) in enumerate(_text_overlays(edl)):
        parts.append(
            f"{vlabel}drawtext="
            f"text='{_escape_drawtext(overlay['text'])}':"
            f"x=(w-text_w)*{overlay['x']}:"
            f"y=(h-text_h)*{overlay['y']}:"
            f"fontsize={overlay['fontSize']}:"
            f"fontcolor={overlay['color']}:"
            f"enable='between(t,{_fmt(t_start)},{_fmt(t_end)})'"
            f"[vt{k}]"
        )
        vlabel = f"[vt{k}]"

    # -- audio: trim, place on timeline with adelay, mix -----------------------
    if audio_clips:
        for j, clip in enumerate(audio_clips):
            src_idx = input_index[clip["source"]]
            delay_ms = round(clip["start"] * 1000)
            parts.append(
                f"[{src_idx}:a]"
                f"atrim=start={_fmt(clip['in'])}:end={_fmt(clip['out'])},"
                f"asetpts=PTS-STARTPTS,"
                f"adelay={delay_ms}|{delay_ms}[a{j}]"
            )
        mixed = "".join(f"[a{j}]" for j in range(len(audio_clips)))
        parts.append(
            f"{mixed}amix=inputs={len(audio_clips)}:duration=longest:"
            f"dropout_transition=0:normalize=0[aout]"
        )
        amap = ["-map", "[aout]"]
    else:
        amap = ["-an"]

    cmd += ["-filter_complex", ";".join(parts)]
    cmd += ["-map", vlabel]
    cmd += amap
    cmd += [
        "-c:v", settings.get("video_codec", "libx264"),
        "-preset", settings.get("preset", "medium"),
        "-crf", str(settings.get("crf", 20)),
        "-c:a", settings.get("audio_codec", "aac"),
        "-b:a", settings.get("audio_bitrate", "192k"),
        "-movflags", "+faststart",
        output_path,
    ]
    return cmd
