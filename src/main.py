from audio import aligned_audio_filter
from config import OUTPUT_FPS
from media import run


def aligned_video_filter(input_index, shift, duration, width, height, label):
    """Build the filter that aligns one camera picture to VIDEO's timeline."""
    filters = ["setpts=PTS-STARTPTS"]

    if shift >= 0:
        filters.append(f"trim=start={shift:.6f}")
    else:
        filters.append(
            f"tpad=start_mode=clone:start_duration={abs(shift):.6f}"
        )

    filters.extend([
        "setpts=PTS-STARTPTS",
        f"tpad=stop_mode=clone:stop_duration={duration:.6f}",
        f"trim=duration={duration:.6f}",
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "setsar=1",
        f"fps={OUTPUT_FPS}",
        "format=yuv420p",
    ])
    return f"[{input_index}:v:0]{','.join(filters)}[{label}]"


def camera_cut_filters(camera_by_frame, duration, envelope_rate):
    """Build a concat graph switching cameras according to per-frame choices."""
    frame_count = len(camera_by_frame)
    if frame_count == 0:
        raise ValueError("No camera-selection frames were generated")

    boundaries = [
        i for i in range(1, frame_count)
        if camera_by_frame[i] != camera_by_frame[i - 1]
    ]
    starts = [0, *boundaries]
    ends = [*boundaries, frame_count]

    count_by_camera = {
        1: sum(camera_by_frame[start] == 1 for start in starts),
        2: sum(camera_by_frame[start] == 2 for start in starts),
    }
    filters = []

    for camera_number in (1, 2):
        count = count_by_camera[camera_number]
        if count:
            label = f"v{camera_number}"
            filters.append(
                f"[{label}]split={count}"
                + "".join(f"[{label}s{i}]" for i in range(count))
            )

    camera_indices = {1: 0, 2: 0}
    segment_labels = []

    for segment_number, (start_frame, end_frame) in enumerate(zip(starts, ends)):
        start = start_frame / envelope_rate
        end = min(end_frame / envelope_rate, duration)
        segment_duration = end - start
        camera_number = int(camera_by_frame[start_frame])
        source = f"[v{camera_number}s{camera_indices[camera_number]}]"
        camera_indices[camera_number] += 1
        label = f"segment{segment_number}"

        filters.append(
            f"{source}trim=start={start:.6f}:duration={segment_duration:.6f},"
            f"setpts=PTS-STARTPTS[{label}]"
        )
        segment_labels.append(f"[{label}]")

    filters.append(
        f"{''.join(segment_labels)}concat=n={len(segment_labels)}:v=1:a=0[vout]"
    )
    return ";".join(filters)


def render_video(
    video1,
    audio1,
    audio2,
    video2,
    output,
    duration,
    width,
    height,
    shift1,
    shift2,
    video2_shift,
    camera_by_frame,
    envelope_rate,
):
    """Construct the FFmpeg graph and render the switched video."""
    audio1_filter = aligned_audio_filter(1, shift1, duration)
    audio2_filter = aligned_audio_filter(2, shift2, duration)
    video1_filter = aligned_video_filter(0, 0.0, duration, width, height, "v1")
    video2_filter = aligned_video_filter(
        3, video2_shift, duration, width, height, "v2"
    )

    filter_complex = (
        f"{audio1_filter}[a1];"
        f"{audio2_filter}[a2];"
        "[a1][a2]"
        "amix=inputs=2:duration=longest:dropout_transition=0:"
        "weights='1 1':normalize=0,"
        "alimiter=limit=0.95"
        "[merged];"
        f"{video1_filter};"
        f"{video2_filter};"
        f"{camera_cut_filters(camera_by_frame, duration, envelope_rate)}"
    )

    print(f"Writing {output} with activity-driven camera switching...")
    run([
        "ffmpeg", "-y",
        "-i", str(video1),
        "-i", str(audio1),
        "-i", str(audio2),
        "-i", str(video2),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[merged]",
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        str(output),
    ])
