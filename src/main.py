import subprocess
import tempfile
from pathlib import Path

from audio import aligned_audio_filter, prepare_audio
from camera import choose_camera_by_activity, export_camera_cuts
from config import (
    AUDIO1,
    AUDIO2,
    CUTS_JSON,
    ENVELOPE_RATE,
    MIN_CORRELATION,
    OUTPUT,
    VIDEO,
    VIDEO2,
)
from media import extract_analysis_wav, probe_duration, probe_video_size
from rendering import render_video
from sync import estimate_and_check


def validate_inputs():
    for path in (VIDEO, VIDEO2, AUDIO1, AUDIO2):
        if not Path(path).exists():
            raise FileNotFoundError(path)


def main():
    validate_inputs()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        processed_audio1 = prepare_audio(
            AUDIO1, temp_dir / "audio1_processed.wav"
        )
        processed_audio2 = prepare_audio(
            AUDIO2, temp_dir / "audio2_processed.wav"
        )

        video_duration = probe_duration(VIDEO)
        width, height = probe_video_size(VIDEO)

        video_wav = temp_dir / "video_audio.wav"
        video2_wav = temp_dir / "video2_audio.wav"
        audio1_wav = temp_dir / "audio1.wav"
        audio2_wav = temp_dir / "audio2.wav"

        print("Extracting analysis audio...")
        try:
            extract_analysis_wav(VIDEO, video_wav)
        except subprocess.CalledProcessError as exc:
            raise SystemExit(
                "Could not extract audio from VIDEO. This workflow needs "
                "VIDEO's embedded audio as its sync reference."
            ) from exc

        try:
            extract_analysis_wav(VIDEO2, video2_wav)
        except subprocess.CalledProcessError as exc:
            raise SystemExit(
                "Could not extract audio from VIDEO2. This workflow uses "
                "VIDEO2's embedded audio to sync its picture to VIDEO."
            ) from exc

        extract_analysis_wav(processed_audio1, audio1_wav)
        extract_analysis_wav(processed_audio2, audio2_wav)

        video2_shift = estimate_and_check(
            video_wav, video2_wav, "VIDEO2", MIN_CORRELATION
        )
        shift1 = estimate_and_check(
            video_wav, audio1_wav, "AUDIO1", MIN_CORRELATION
        )
        shift2 = estimate_and_check(
            video_wav, audio2_wav, "AUDIO2", MIN_CORRELATION
        )

        camera_by_frame = choose_camera_by_activity(
            audio1_wav, audio2_wav, shift1, shift2, video_duration
        )
        export_camera_cuts(CUTS_JSON, camera_by_frame, video_duration)

        render_video(
            VIDEO,
            processed_audio1,
            processed_audio2,
            VIDEO2,
            OUTPUT,
            video_duration,
            width,
            height,
            shift1,
            shift2,
            video2_shift,
            camera_by_frame,
            aligned_audio_filter,
            ENVELOPE_RATE,
        )

    print(f"Done: {OUTPUT}")


if __name__ == "__main__":
    main()
