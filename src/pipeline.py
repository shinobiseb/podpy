import subprocess
import tempfile
from pathlib import Path

from audio import prepare_audio
from camera import choose_camera_by_activity, export_camera_cuts
from config import ENVELOPE_RATE, MIN_CORRELATION
from media import extract_analysis_wav, probe_duration, probe_video_size
from rendering import render_video
from sync import estimate_and_check


def process_project(video1, video2, audio1, audio2, output, cuts_json, on_progress=None):
    """Run the complete sync, camera-selection, and render workflow."""
    def report(message):
        print(message)
        if on_progress:
            on_progress(message)

    inputs = (video1, video2, audio1, audio2)
    for path in inputs:
        if not Path(path).is_file():
            raise FileNotFoundError(f"Input file not found: {path}")

    report("Preparing audio tracks (loudness check and processing if needed)...")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        prepared_audio1 = prepare_audio(audio1, temp_dir / "audio1_processed.wav")
        prepared_audio2 = prepare_audio(audio2, temp_dir / "audio2_processed.wav")

        report("Inspecting reference video...")
        duration = probe_duration(video1)
        width, height = probe_video_size(video1)

        video1_wav = temp_dir / "video1_analysis.wav"
        video2_wav = temp_dir / "video2_analysis.wav"
        audio1_wav = temp_dir / "audio1_analysis.wav"
        audio2_wav = temp_dir / "audio2_analysis.wav"

        report("Extracting audio for sync analysis...")
        try:
            extract_analysis_wav(video1, video1_wav)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Could not extract audio from the first video; it is used as the sync reference."
            ) from exc

        try:
            extract_analysis_wav(video2, video2_wav)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Could not extract audio from the second video for picture sync."
            ) from exc

        extract_analysis_wav(prepared_audio1, audio1_wav)
        extract_analysis_wav(prepared_audio2, audio2_wav)

        report("Estimating sync offsets...")
        video2_shift = estimate_and_check(
            video1_wav, video2_wav, "VIDEO2", MIN_CORRELATION
        )
        audio1_shift = estimate_and_check(
            video1_wav, audio1_wav, "AUDIO1", MIN_CORRELATION
        )
        audio2_shift = estimate_and_check(
            video1_wav, audio2_wav, "AUDIO2", MIN_CORRELATION
        )

        report("Selecting camera cuts...")
        camera_by_frame = choose_camera_by_activity(
            audio1_wav, audio2_wav, audio1_shift, audio2_shift, duration
        )
        export_camera_cuts(
            cuts_json, camera_by_frame, duration, video1, video2
        )

        report("Rendering final video. This may take a while...")
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
