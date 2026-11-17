import subprocess
import tempfile
from pathlib import Path

from audio import prepare_audio
from camera import choose_camera_by_activity, export_camera_cuts, export_fcpxml
from config import ENVELOPE_RATE, MIN_CORRELATION
from media import extract_analysis_wav, extract_audio_track, probe_duration, probe_video_size
from rendering import render_video
from sync import estimate_and_check


def process_project(
    video1,
    video2,
    audio1=None,
    audio2=None,
    output="Synced_video.mp4",
    cuts_json="camera_cuts.json",
    final_cut_xml=None,
    on_progress=None,
):
    """Sync two videos, choose camera cuts, and render the multicamera edit.

    If both audio paths are omitted, each video's embedded audio is used for
    synchronization, activity detection, and the final audio mix.
    """
    def report(message):
        print(message)
        if on_progress:
            on_progress(message)

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

        if video_only_mode:
            report("Video-only mode: extracting embedded audio tracks...")
            embedded_audio1 = temp_dir / "video1_embedded_audio.wav"
            embedded_audio2 = temp_dir / "video2_embedded_audio.wav"
            try:
                extract_audio_track(video1, embedded_audio1)
                extract_audio_track(video2, embedded_audio2)
            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    "Could not extract embedded audio. Both videos must contain an audio track."
                ) from exc
            prepared_audio1 = prepare_audio(
                embedded_audio1, temp_dir / "video1_processed.wav"
            )
            prepared_audio2 = prepare_audio(
                embedded_audio2, temp_dir / "video2_processed.wav"
            )
        else:
            report("Preparing external audio tracks (loudness check and processing if needed)...")
            prepared_audio1 = prepare_audio(audio1, temp_dir / "audio1_processed.wav")
            prepared_audio2 = prepare_audio(audio2, temp_dir / "audio2_processed.wav")

        report("Inspecting reference video...")
        duration = probe_duration(video1)
        width, height = probe_video_size(video1)

        video1_wav = temp_dir / "video1_analysis.wav"
        video2_wav = temp_dir / "video2_analysis.wav"
        report("Extracting audio for sync analysis...")
        try:
            extract_analysis_wav(video1, video1_wav)
            extract_analysis_wav(video2, video2_wav)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Could not extract audio for sync analysis. Both videos must contain audio."
            ) from exc

        report("Estimating sync offsets...")
        video2_shift = estimate_and_check(
            video1_wav, video2_wav, "VIDEO2", MIN_CORRELATION
        )

        if video_only_mode:
            # The first camera defines the timeline. Its embedded audio is
            # therefore unshifted; camera 2's audio follows camera 2's sync.
            audio1_shift = 0.0
            audio2_shift = video2_shift
            activity_audio1 = video1_wav
            activity_audio2 = video2_wav
        else:
            audio1_wav = temp_dir / "audio1_analysis.wav"
            audio2_wav = temp_dir / "audio2_analysis.wav"
            extract_analysis_wav(prepared_audio1, audio1_wav)
            extract_analysis_wav(prepared_audio2, audio2_wav)
            audio1_shift = estimate_and_check(
                video1_wav, audio1_wav, "AUDIO1", MIN_CORRELATION
            )
            audio2_shift = estimate_and_check(
                video1_wav, audio2_wav, "AUDIO2", MIN_CORRELATION
            )
            activity_audio1 = audio1_wav
            activity_audio2 = audio2_wav

        report("Selecting camera cuts...")
        camera_by_frame = choose_camera_by_activity(
            activity_audio1, activity_audio2, audio1_shift, audio2_shift, duration
        )
        export_camera_cuts(cuts_json, camera_by_frame, duration, video1, video2)
        if final_cut_xml:
            export_fcpxml(final_cut_xml, camera_by_frame, duration, video1, video2)

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
    if final_cut_xml:
        report(f"Final Cut Pro XML: {final_cut_xml}")
