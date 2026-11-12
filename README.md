# PodPy

A small local Python prototype for creating an audio-driven multicam edit from two video sources and two separate audio tracks.

The app checks audio loudness, optionally applies voice processing, estimates sync offsets, chooses the active camera based on microphone activity, exports a JSON cut list, and renders the final video with FFmpeg.

## Project structure

- `src/main.py` — workflow orchestration and entry point
- `src/config.py` — input/output paths and processing settings
- `src/media.py` — FFmpeg/ffprobe helpers and WAV analysis I/O
- `src/audio.py` — loudness measurement, voice processing, audio alignment filters
- `src/sync.py` — audio-envelope sync estimation
- `src/camera.py` — activity detection, camera selection, cut-list export
- `src/rendering.py` — video filters, camera cuts, final FFmpeg render
- `requirements.txt` — Python dependencies

## Requirements

- Python 3.9+
- FFmpeg and ffprobe installed and available in your PATH
- Dependencies installed in a virtual environment

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure and run

Edit the media paths and settings in `src/config.py`:

```python
VIDEO = "src/files/pov_seb.mp4"
VIDEO2 = "src/files/pov_gus.mp4"
AUDIO1 = "src/files/pod1_seb.mp3"
AUDIO2 = "src/files/pod1_gus.mp3"
OUTPUT = "Synced_video.mp4"
```

Run the workflow from the repository root:

```bash
python src/main.py
```

For each audio track, the script measures integrated loudness (LUFS) and true peak (dBTP). It uses the original if it is within the configured LUFS tolerance and below the true-peak ceiling; otherwise it makes a processed temporary WAV. The processed/original prepared tracks are used consistently for sync analysis, activity detection, and the final render. Temporary audio is removed when the run finishes.

The processing chain (gate, high-pass/EQ, compressor, and loudness normalization) is a starting point, not a universal preset. Tune the parameters in `src/config.py` for the speaker, microphone, and room. Loudness measurement cannot determine whether a gate/EQ/compressor was previously applied; it only checks measured loudness and peak.

The script writes the final video to `OUTPUT` and a reviewable camera cut list to `CUTS_JSON`.
