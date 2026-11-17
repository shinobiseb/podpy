import subprocess
import tempfile
from pathlib import Path

from audio import prepare_audio
from camera import choose_camera_by_activity, export_camera_cuts, export_fcpxml
from config import ENVELOPE_RATE, MIN_CORRELATION
from media import extract_analysis_wav, extract_audio_track, probe_duration, probe_video_size
from rendering import render_video
from sync import estimate_and_check


OUTPUT_MODES = ("render", "resolve", "both")


def process_project(
    video1,
    video2,
    audio1=None,
    audio2=None,
    output=None,
    cuts_json="camera_cuts.json",
    resolve_xml=None,
    output_mode="render",
    on_progress=None,
):
    """Analyze two cameras, then render an MP4, export a Resolve timeline XML, or both.

    Omitting both audio paths selects embedded-audio mode. Resolve-only mode
    skips audio mastering and video rendering; it writes a timeline XML that
    references the original video files and their cut segments.
    """
    def report(message):
        print(message)
        if on_progress:
            on_progress(message)

    if output_mode not in OUTPUT_MODES:
        raise ValueError(f"output_mode must be one of {', '.join(OUTPUT_MODES)}")
    render_requested = output_mode in ("render", "both")
    timeline_requested = output_mode in ("resolve", "both")
    if render_requested and not output:
        raise ValueError("An MP4 output path is required for render/both mode.")
    if timeline_requested and not resolve_xml:
        raise ValueError("A Resolve XML path is required for resolve/both mode.")

    for path in (video1, video2):
        if not Path(path).is_file():
            raise FileNotFoundError(f"Input video not found: {path}")

    if (audio1 is None) != (audio2 is None):
        raise ValueError("Provide either both external audio tracks or neither.")

    video_only_mode = audio1 is None
    if not video_only_mode:
        for path in (audio1, audio2):
            if not Path(path).is_file():
                raise FileNotFoundError(f"Input audio file not found: {path}")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        video1_wav = temp_dir / "video1_analysis.wav"
        video2_wav = temp_dir / "video2_analysis.wav"

        if video_only_mode:
            report("Video-only mode: extracting embedded audio for analysis...")
            try:
                extract_analysis_wav(video1, video1_wav)
                extract_analysis_wav(video2, video2_wav)
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    "Could not extract embedded audio. Both videos must contain audio."
                ) from exc
            activity_audio1, activity_audio2 = video1_wav, video2_wav
            audio1_shift = 0.0
        else:
            activity_audio1 = temp_dir / "audio1_analysis.wav"
            activity_audio2 = temp_dir / "audio2_analysis.wav"

        if render_requested:
            if video_only_mode:
                report("Extracting full embedded audio for the MP4...")
                embedded_audio1 = temp_dir / "video1_embedded_audio.wav"
                embedded_audio2 = temp_dir / "video2_embedded_audio.wav"
                try:
                    extract_audio_track(video1, embedded_audio1)
                    extract_audio_track(video2, embedded_audio2)
                except subprocess.CalledProcessError as exc:
                    raise RuntimeError(
                        "Could not extract embedded audio. Both videos must contain audio."
                    ) from exc
                prepared_audio1 = prepare_audio(
                    embedded_audio1, temp_dir / "video1_processed.wav"
                )
                prepared_audio2 = prepare_audio(
                    embedded_audio2, temp_dir / "video2_processed.wav"
                )
            else:
                report("Preparing external audio tracks for the MP4...")
                prepared_audio1 = prepare_audio(audio1, temp_dir / "audio1_processed.wav")
                prepared_audio2 = prepare_audio(audio2, temp_dir / "audio2_processed.wav")

        report("Inspecting videos...")
        duration1 = probe_duration(video1)
        duration2 = probe_duration(video2)
        duration = duration1
        width, height = probe_video_size(video1)
        default_camera = 2 if duration2 > duration1 else 1
        report(
            f"Default camera during silence: VIDEO{default_camera} "
            f"(longer clip; VIDEO1 {duration1:.1f}s, VIDEO2 {duration2:.1f}s)"
        )

        report("Extracting audio for sync analysis...")
        try:
            if not video_only_mode:
                extract_analysis_wav(
                    prepared_audio1 if render_requested else audio1, activity_audio1
                )
                extract_analysis_wav(
                    prepared_audio2 if render_requested else audio2, activity_audio2
                )
            extract_analysis_wav(video1, video1_wav)
            extract_analysis_wav(video2, video2_wav)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Could not extract audio for analysis. Check that the selected media contains audio."
            ) from exc

        report("Estimating sync offsets...")
        video2_shift = estimate_and_check(
            video1_wav, video2_wav, "VIDEO2", MIN_CORRELATION
        )

        if video_only_mode:
            audio2_shift = video2_shift
        else:
            audio1_shift = estimate_and_check(
                video1_wav, activity_audio1, "AUDIO1", MIN_CORRELATION
            )
            audio2_shift = estimate_and_check(
                video1_wav, activity_audio2, "AUDIO2", MIN_CORRELATION
            )

        report("Selecting camera cuts...")
        camera_by_frame = choose_camera_by_activity(
            activity_audio1,
            activity_audio2,
            audio1_shift,
            audio2_shift,
            duration,
            default_camera=default_camera,
        )
        export_camera_cuts(cuts_json, camera_by_frame, duration, video1, video2)

        if timeline_requested:
            report("Creating Resolve timeline XML...")
            export_fcpxml(
                resolve_xml,
                camera_by_frame,
                duration,
                video1,
                video2,
            )
            report(f"Resolve XML: {resolve_xml}")

        if render_requested:
            report("Rendering final MP4. This may take a while...")
            render_video(
                video1=video1,
                audio1=prepared_audio1,
                audio2=prepared_audio2,
                video2=video2,
                output=output,
                duration=duration,
                width=width,
                height=height,
                shift1=audio1_shift,
                shift2=audio2_shift,
                video2_shift=video2_shift,
                camera_by_frame=camera_by_frame,
                envelope_rate=ENVELOPE_RATE,
            )
            report(f"Finished: {output}")

    report(f"Camera cut list: {cuts_json}")
