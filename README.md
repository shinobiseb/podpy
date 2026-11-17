# PodPy

A local desktop-friendly tool that creates an audio-driven multicamera podcast edit from two videos and two separate audio tracks.

## Windows setup

Install Python 3 and FFmpeg (including `ffmpeg` and `ffprobe`) and ensure both FFmpeg commands are on `PATH`. Put the four media inputs in `src/files/`:

- `pov_seb.mp4` — reference camera video, with embedded audio
- `pov_gus.mp4` — second camera video, with embedded sync audio
- `pod1_seb.mp3` — first microphone track
- `pod1_gus.mp3` — second microphone track

Run `setup_windows.bat` once, then `run_windows.bat`. The scripts use the repository's Windows virtual environment. For complete setup details and troubleshooting, see [WINDOWS_SETUP.md](WINDOWS_SETUP.md).

## Other platforms

Python 3.9+, FFmpeg/ffprobe, and dependencies in `requirements.txt` are required. Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the command-line application with the configured default input paths:

```bash
python src/main.py
```

## Processing and outputs

PodPy checks the microphone tracks' loudness and processes tracks that are outside the configured target. It estimates sync against the first video's embedded audio, selects camera cuts from mic activity, exports a JSON cut list and a Final Cut Pro XML timeline, then renders the combined video and audio locally.

The default outputs are `Synced_video.mp4`, `test_synced_merged_cuts.json`, and `Synced_video.fcpxml` in the repository root. Rendering prefers NVIDIA NVENC (`h264_nvenc`) when FFmpeg advertises it and falls back to `libx264` otherwise. Temporary analysis and processed audio files are cleaned up automatically.
