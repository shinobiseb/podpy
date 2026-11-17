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


def _frame_time(frame_number):
    """Format a frame index as an FCPXML rational time at the project rate."""
    return f"{max(0, int(frame_number))}/{OUTPUT_FPS}s"


def export_fcpxml(
    path,
    camera_by_frame,
    duration,
    video1=VIDEO,
    video2=VIDEO2,
    video1_duration=None,
    video2_duration=None,
    video2_shift=0.0,
    width=1920,
    height=1080,
):
    """Write a Resolve-importable FCPXML sequence with valid source references."""
    if len(camera_by_frame) == 0:
        raise ValueError("No camera-selection frames were generated")

    sources = {
        1: (Path(video1).expanduser().resolve(), float(video1_duration or duration), 0.0, "r2"),
        2: (Path(video2).expanduser().resolve(), float(video2_duration or duration), float(video2_shift), "r3"),
    }
    project_frames = max(1, round(duration * OUTPUT_FPS))
    fcpxml = ET.Element("fcpxml", version="1.8")
    resources = ET.SubElement(fcpxml, "resources")
    ET.SubElement(
        resources,
        "format",
        id="r1",
        name=f"FFVideoFormat{height}p{OUTPUT_FPS}",
        frameDuration=f"1/{OUTPUT_FPS}s",
        width=str(width),
        height=str(height),
    )
    for source, source_duration, _shift, asset_id in sources.values():
        ET.SubElement(
            resources,
            "asset",
            id=asset_id,
            name=source.name,
            src=source.as_uri(),
            start="0s",
            duration=_frame_time(round(source_duration * OUTPUT_FPS)),
            hasVideo="1",
            hasAudio="1",
            format="r1",
        )

    library = ET.SubElement(fcpxml, "library")
    event = ET.SubElement(library, "event", name="PodPy")
    project = ET.SubElement(event, "project", name="PodPy Auto Cut")
    sequence = ET.SubElement(
        project,
        "sequence",
        format="r1",
        duration=_frame_time(project_frames),
        tcStart="0s",
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate="48k",
    )
    spine = ET.SubElement(sequence, "spine")

    timeline_cursor = 0
    for segment_number, segment in enumerate(_cut_segments(camera_by_frame, duration), start=1):
        segment_start = max(0, round(segment["start_seconds"] * OUTPUT_FPS))
        segment_end = min(project_frames, round(segment["end_seconds"] * OUTPUT_FPS))
        if segment_end <= segment_start:
            continue
        camera = segment["camera_number"]
        source, source_duration, shift, asset_id = sources[camera]
        shift_frames = round(shift * OUTPUT_FPS)
        source_end = round(source_duration * OUTPUT_FPS)
        valid_start = max(segment_start, -shift_frames)
        valid_end = min(segment_end, source_end - shift_frames)

        if valid_start > timeline_cursor:
            ET.SubElement(
                spine,
                "gap",
                name="Unavailable source frames",
                offset=_frame_time(timeline_cursor),
                duration=_frame_time(valid_start - timeline_cursor),
            )
            timeline_cursor = valid_start
        if valid_end > valid_start:
            if valid_start > timeline_cursor:
                ET.SubElement(
                    spine,
                    "gap",
                    name="Timeline gap",
                    offset=_frame_time(timeline_cursor),
                    duration=_frame_time(valid_start - timeline_cursor),
                )
                timeline_cursor = valid_start
            clip_frames = valid_end - valid_start
            source_start = valid_start + shift_frames
            ET.SubElement(
                spine,
                "asset-clip",
                name=f"VIDEO{camera} segment {segment_number}",
                ref=asset_id,
                offset=_frame_time(timeline_cursor),
                start=_frame_time(source_start),
                duration=_frame_time(clip_frames),
            )
            timeline_cursor += clip_frames
        if timeline_cursor < segment_end:
            ET.SubElement(
                spine,
                "gap",
                name="Unavailable source frames",
                offset=_frame_time(timeline_cursor),
                duration=_frame_time(segment_end - timeline_cursor),
            )
            timeline_cursor = segment_end

    if timeline_cursor < project_frames:
        ET.SubElement(
            spine,
            "gap",
            name="End of timeline",
            offset=_frame_time(timeline_cursor),
            duration=_frame_time(project_frames - timeline_cursor),
        )

    ET.indent(fcpxml, space="  ")
    ET.ElementTree(fcpxml).write(path, encoding="utf-8", xml_declaration=True)
    print(f"Saved FCPXML timeline to {path}")
