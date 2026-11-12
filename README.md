# PodPy

A local desktop-friendly tool that creates an audio-driven multicamera podcast edit from two videos and two separate audio tracks.

## Desktop app

The simple Tkinter interface lets you browse for both video files, both audio tracks, and choose where the rendered MP4 and camera cut-list JSON should be saved. Processing runs locally on your computer.

```bash
python src/gui.py
```

Select the four inputs and output destinations, then click **Process video**. The app checks/normalizes the audio as needed, estimates sync, chooses camera cuts from mic activity, and renders the output. Keep the app open until rendering finishes.

## Requirements

- Python 3.9+
- FFmpeg and ffprobe installed and available on your PATH
- Dependencies installed in a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Tkinter is included with many Python installations. On some Linux distributions it must be installed separately (for example, the `python3-tk` system package).

## Command-line mode

To run with the default file paths configured in `src/config.py`:

```bash
python src/main.py
```

## Processing notes

The app checks integrated loudness and true peak. Tracks outside the configured target are processed with a gate, high-pass/EQ, compressor, and loudness normalization. These are starting values; adjust them in `src/config.py` for your microphones and room. Loudness checking does not prove that the filters were previously applied.

The video and cut list are written to the destinations selected in the app. Temporary analysis and processed audio files are cleaned up automatically.
