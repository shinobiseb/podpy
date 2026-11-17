import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from config import (
    ACTIVITY_ABOVE_NOISE_DB,
    ACTIVITY_FLOOR_DBFS,
    ENVELOPE_RATE,
    MAX_SILENCE_GAP_SECONDS,
    MIN_ACTIVITY_SECONDS,
    OUTPUT_FPS,
    VIDEO,
    VIDEO2,
)
from media import read_pcm16_wav


def _filter_short_runs(mask, value, max_length, replacement):
    """Replace runs of `value` shorter than or equal to max_length."""
    result = mask.copy()
    changes = np.diff(np.r_[False, result == value, False].astype(np.int8))
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1)
    for start, end in zip(starts, ends):
        if end - start <= max_length:
            result[start:end] = replacement
    return result


def _cut_segments(camera_by_frame, duration):
    boundaries = np.flatnonzero(camera_by_frame[1:] != camera_by_frame[:-1]) + 1
    starts = np.r_[0, boundaries]
    ends = np.r_[boundaries, len(camera_by_frame)]
    segments = []
    for start_frame, end_frame in zip(starts, ends):
        start = start_frame / ENVELOPE_RATE
        end = min(end_frame / ENVELOPE_RATE, duration)
        segments.append({
            "start_seconds": start,
            "end_seconds": end,
            "duration_seconds": end - start,
            "camera_number": int(camera_by_frame[start_frame]),
        })
    return segments


def audio_activity_on_timeline(path, shift, duration):
    """Compute activity in short frames aligned to VIDEO1's timeline."""
    rate, samples = read_pcm16_wav(path)
    frame_size = rate // ENVELOPE_RATE
    if frame_size <= 0:
        raise ValueError(f"Invalid analysis rate in {path}")
    frame_count = len(samples) // frame_size
    if frame_count == 0:
        raise ValueError(f"No audio available for activity analysis in {path}")
    frames = samples[:frame_count * frame_size].reshape(frame_count, frame_size)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    dbfs = 20.0 * np.log10(np.maximum(rms, 1e-8))
    noise_floor = float(np.percentile(dbfs, 20))
    threshold = max(ACTIVITY_FLOOR_DBFS, noise_floor + ACTIVITY_ABOVE_NOISE_DB)
    active = dbfs >= threshold
    active = _filter_short_runs(
        active, False, round(MAX_SILENCE_GAP_SECONDS * ENVELOPE_RATE), True
    )
    active = _filter_short_runs(
        active, True, round(MIN_ACTIVITY_SECONDS * ENVELOPE_RATE), False
    )
    timeline = np.zeros(math.ceil(duration * ENVELOPE_RATE), dtype=bool)
    source_times = np.arange(frame_count) / ENVELOPE_RATE
    indices = np.rint((source_times - shift) * ENVELOPE_RATE).astype(np.int64)
    valid = (indices >= 0) & (indices < len(timeline)) & active
    timeline[indices[valid]] = True
    return timeline


def choose_camera_by_activity(
    audio1_wav, audio2_wav, shift1, shift2, duration, default_camera=1
):
    """Choose by activity, defaulting to the selected camera during silence."""
    if default_camera not in (1, 2):
        raise ValueError("default_camera must be 1 or 2")
    active1 = audio_activity_on_timeline(audio1_wav, shift1, duration)
    active2 = audio_activity_on_timeline(audio2_wav, shift2, duration)
    camera = np.full(len(active1), default_camera, dtype=np.int8)
    current = default_camera
    was_active1 = was_active2 = False
    for i, (is_active1, is_active2) in enumerate(zip(active1, active2)):
        onset1 = is_active1 and not was_active1
        onset2 = is_active2 and not was_active2
        if is_active1 and not is_active2:
            current = 1
        elif is_active2 and not is_active1:
            current = 2
        elif is_active1 and is_active2:
            if onset1 and not onset2:
                current = 1
            elif onset2 and not onset1:
                current = 2
        camera[i] = current
        was_active1, was_active2 = is_active1, is_active2
    return camera


def export_camera_cuts(path, camera_by_frame, duration, video1=VIDEO, video2=VIDEO2):
    """Save camera selections as an inspectable JSON cut list."""
    if len(camera_by_frame) == 0:
        raise ValueError("No camera-selection frames were generated")
    cuts = []
    for segment in _cut_segments(camera_by_frame, duration):
        cuts.append({
            "start_seconds": round(segment["start_seconds"], 3),
            "end_seconds": round(segment["end_seconds"], 3),
            "duration_seconds": round(segment["duration_seconds"], 3),
            "camera": f"VIDEO{segment['camera_number']}",
        })
    data = {
        "video_duration_seconds": round(duration, 3),
        "envelope_rate": ENVELOPE_RATE,
        "camera_sources": {"VIDEO1": str(video1), "VIDEO2": str(video2)},
        "cuts": cuts,
    }
    with open(path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2)
        json_file.write("\n")
    print(f"Saved {len(cuts)} camera cuts to {path}")


def _timecode(seconds):
    """Format non-drop-frame timecode at the configured timeline frame rate."""
    total_frames = max(0, round(seconds * OUTPUT_FPS))
    frames = total_frames % OUTPUT_FPS
    total_seconds = total_frames // OUTPUT_FPS
    ss = total_seconds % 60
    total_minutes = total_seconds // 60
    mm = total_minutes % 60
    hh = total_minutes // 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{frames:02d}"


def export_resolve_edl(
    path,
    camera_by_frame,
    duration,
    video1,
    video2,
    video1_duration,
    video2_duration,
    video2_shift,
    default_camera=1,
):
    """Write a CMX 3600 EDL with source clip cuts and sync-adjusted source in-points.

    The EDL references original files by clip name/reel comments. Resolve may
    prompt to relink these files during import. Audio is intentionally omitted.
    """
    if len(camera_by_frame) == 0:
        raise ValueError("No camera-selection frames were generated")

    paths = {1: str(video1), 2: str(video2)}
    durations = {1: float(video1_duration), 2: float(video2_duration)}
    shifts = {1: 0.0, 2: float(video2_shift)}
    segments = _cut_segments(camera_by_frame, duration)
    lines = ["TITLE: PodPy Auto Cut", "FCM: NON-DROP FRAME", ""]
    event_number = 1

    for segment in segments:
        timeline_start = segment["start_seconds"]
        timeline_end = segment["end_seconds"]
        camera = segment["camera_number"]

        # If a selected camera has no source frames for this interval, use the
        # longer/default camera when possible, otherwise the other valid source.
        candidates = [camera, default_camera, 1 if camera == 2 else 2]
        chosen = None
        for candidate in candidates:
            source_start = timeline_start + shifts[candidate]
            source_end = timeline_end + shifts[candidate]
            if source_start >= 0 and source_end <= durations[candidate]:
                chosen = candidate
                break
        if chosen is None:
            # Keep the timeline continuous by trimming the selected interval to
            # the valid source range when a sync offset reaches a clip boundary.
            for candidate in candidates:
                valid_start = max(timeline_start, -shifts[candidate])
                valid_end = min(timeline_end, durations[candidate] - shifts[candidate])
                if valid_end - valid_start > 1.0 / OUTPUT_FPS:
                    chosen = candidate
                    timeline_start, timeline_end = valid_start, valid_end
                    break
        if chosen is None or timeline_end <= timeline_start:
            continue

        source_start = timeline_start + shifts[chosen]
        source_end = timeline_end + shifts[chosen]
        reel = f"CAM{chosen}"
        lines.append(
            f"{event_number:03d}  {reel:<8} V     C        "
            f"{_timecode(source_start)} {_timecode(source_end)} "
            f"{_timecode(timeline_start)} {_timecode(timeline_end)}"
        )
        lines.append(f"* FROM CLIP NAME: {Path(paths[chosen]).name}")
        lines.append(f"* SOURCE FILE: {Path(paths[chosen]).resolve()}")
        lines.append("")
        event_number += 1

    if event_number == 1:
        raise ValueError("No valid source intervals could be written to the EDL")
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {event_number - 1} Resolve EDL events to {path}")
