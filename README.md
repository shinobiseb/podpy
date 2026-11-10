# PodPy

A small Python prototype for creating an audio-driven multicam edit from two synced video sources and two audio sources.

The script analyzes the audio tracks, estimates sync offsets, decides which camera should be active based on microphone activity, exports a JSON cut list, and renders a final video with FFmpeg.

## What it does

- Reads two video files and two audio files
- Checks that the media files exist and are readable
- Uses FFprobe to inspect media metadata
- Aligns audio/video streams by estimating audio offsets
- Detects activity in each source
- Chooses the active camera based on which mic is speaking
- Saves a cut list to JSON for review
- Renders a switched video output with FFmpeg

## Project structure

- `src/main.py` — main processing script
- `requirements.txt` — Python dependencies
- `test_synced_merged_cuts.json` — sample output of detected cuts
- `PROJECT_NOTES.md` — project notes and design ideas

## Requirements

- Python 3.9+
- FFmpeg and ffprobe installed and available in your PATH
- A virtual environment is recommended

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Edit the media file paths in `src/main.py` if needed:

```python
VIDEO = "src/files/pov_seb.mp4"
VIDEO2 = "src/files/pov_gus.mp4"
AUDIO1 = "src/files/pod1_seb.mp3"
AUDIO2 = "src/files/pod1_gus.mp3"
OUTPUT = "Synced_video.mp4"
```

Then run:

```bash
python src/main.py
```

This will:

- analyze the audio,
- generate a cut timeline,
- save `test_synced_merged_cuts.json`, and
- write the final render to `Synced_video.mp4`.

## Notes

This repo is a prototype focused on the core workflow: detect activity, choose the active shot, and render the result. It is intentionally simple and local-first.

## Dependencies

```txt
numpy>=1.23
webrtcvad-wheels>=2.0.14
```
