# PodPy

A local desktop-friendly tool that creates an audio-driven multicamera podcast edit from two videos. It can use either two separate audio tracks or the audio embedded in the videos.

## Desktop app

Launch the Tkinter interface:

```bash
python src/gui.py
```

Choose **Use two separate audio tracks** for the original workflow, or **Videos only** to extract and use each video's embedded audio for sync estimation, speaker activity, camera cuts, and the final audio mix. Both modes can export a rendered MP4, a camera cut-list JSON, and optional Final Cut Pro XML.

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

Use the configured default paths in `src/config.py` with the original separate audio tracks:

```bash
python src/main.py
```

For two-video-only processing, provide video paths and enable embedded audio mode:

```bash
python src/main.py --videos-only \
  --video1 path/to/camera1.mp4 \
  --video2 path/to/camera2.mp4 \
  --output Synced_video.mp4 \
  --cuts-json camera_cuts.json
```

Use `--final-cut-xml path/to/timeline.xml` to also export a Final Cut Pro XML timeline. Both videos need an audio stream with enough shared material for reliable sync estimation (at least 30 seconds of overlap by default).

## Processing notes

PodPy estimates the offset between the two videos from their embedded audio. In videos-only mode, it uses camera 1 as the timeline reference and aligns camera 2's picture and audio to that timeline. Audio activity selects the camera while retaining the current shot during silence. The resulting audio is normalized as needed and mixed into the rendered video.

Rendering uses a continuous two-video overlay with timed camera-two intervals rather than splitting each video into a separate filter branch for every cut. This reduces filter buffering and memory demand on longer recordings, and output timing is fixed to the configured frame rate (30 fps). The output is currently rendered at the first video's resolution.

FFmpeg and ffprobe are required for media inspection, audio extraction, and rendering. Temporary analysis and processed audio files are cleaned up automatically.
