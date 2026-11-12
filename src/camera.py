import json
import math

import numpy as np

from config import (
    ACTIVITY_ABOVE_NOISE_DB,
    ACTIVITY_FLOOR_DBFS,
    ENVELOPE_RATE,
    MAX_SILENCE_GAP_SECONDS,
    MIN_ACTIVITY_SECONDS,
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


def audio_activity_on_timeline(path, shift, duration):
    """Compute activity in 1/ENVELOPE_RATE-second frames on VIDEO's timeline."""
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
    threshold = max(
        ACTIVITY_FLOOR_DBFS,
        noise_floor + ACTIVITY_ABOVE_NOISE_DB,
    )
    source_active = dbfs >= threshold

    gap_frames = round(MAX_SILENCE_GAP_SECONDS * ENVELOPE_RATE)
    min_active_frames = round(MIN_ACTIVITY_SECONDS * ENVELOPE_RATE)
    source_active = _filter_short_runs(source_active, False, gap_frames, True)
    source_active = _filter_short_runs(
        source_active, True, min_active_frames, False
    )

    timeline_count = math.ceil(duration * ENVELOPE_RATE)
    timeline_active = np.zeros(timeline_count, dtype=bool)
    source_times = np.arange(frame_count) / ENVELOPE_RATE
    timeline_indices = np.rint(
        (source_times - shift) * ENVELOPE_RATE
    ).astype(np.int64)

    valid = (
        (timeline_indices >= 0)
        & (timeline_indices < timeline_count)
        & source_active
    )
    timeline_active[timeline_indices[valid]] = True
    return timeline_active


def choose_camera_by_activity(audio1_wav, audio2_wav, shift1, shift2, duration):
    """Choose camera by mic activity, retaining the current shot during silence."""
    active1 = audio_activity_on_timeline(audio1_wav, shift1, duration)
    active2 = audio_activity_on_timeline(audio2_wav, shift2, duration)

    camera = np.ones(len(active1), dtype=np.int8)
    current_camera = 1
    was_active1 = False
    was_active2 = False

    for i, (is_active1, is_active2) in enumerate(zip(active1, active2)):
        onset1 = is_active1 and not was_active1
        onset2 = is_active2 and not was_active2

        if is_active1 and not is_active2:
            current_camera = 1
        elif is_active2 and not is_active1:
            current_camera = 2
        elif is_active1 and is_active2:
            if onset1 and not onset2:
                current_camera = 1
            elif onset2 and not onset1:
                current_camera = 2

        camera[i] = current_camera
        was_active1 = is_active1
        was_active2 = is_active2

    return camera


def export_camera_cuts(path, camera_by_frame, duration):
    """Save contiguous camera selections as an inspectable JSON cut list."""
    if len(camera_by_frame) == 0:
        raise ValueError("No camera-selection frames were generated")

    boundaries = np.flatnonzero(
        camera_by_frame[1:] != camera_by_frame[:-1]
    ) + 1
    starts = np.r_[0, boundaries]
    ends = np.r_[boundaries, len(camera_by_frame)]

    cuts = []
    for start_frame, end_frame in zip(starts, ends):
        start = start_frame / ENVELOPE_RATE
        end = min(end_frame / ENVELOPE_RATE, duration)
        camera_number = int(camera_by_frame[start_frame])
        cuts.append({
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "duration_seconds": round(end - start, 3),
            "camera": f"VIDEO{camera_number}",
        })

    data = {
        "video_duration_seconds": round(duration, 3),
        "envelope_rate": ENVELOPE_RATE,
        "camera_sources": {"VIDEO1": VIDEO, "VIDEO2": VIDEO2},
        "cuts": cuts,
    }

    with open(path, "w", encoding="utf-8") as json_file:
        json.dump(data, json_file, indent=2)
        json_file.write("\n")

    print(f"Saved {len(cuts)} camera cuts to {path}")
