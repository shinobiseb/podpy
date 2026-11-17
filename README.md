# PodPy

A local multicamera editing tool that creates activity-driven cuts from two videos. It can analyze separate audio tracks or use the audio embedded in each video.

## Desktop app

Launch the interface with:

```bash
python src/gui.py
```

Choose the audio source, then select an output workflow:

- **Render MP4** — analyze, cut, and encode the finished video.
- **Create Resolve timeline only** — analyze the audio and write a CMX 3600 EDL referencing the original camera files; skips MP4 rendering and audio mastering.
- **Both MP4 and Resolve timeline** — produce both outputs.

The EDL contains the camera edits and sync-adjusted source in-points. Import it in DaVinci Resolve using **File → Import Timeline → Import AAF, EDL, XML…** and relink the original video files if prompted. The EDL is a video-only edit; arrange/mix audio in Resolve. Resolve may present its normal media-relink dialog, and the exact menu wording can vary by version.

PodPy defaults to whichever input video is longer during detected silence; equal-length clips default to Video 1. Camera 1 remains the synchronization reference and defines the output timeline duration.

## Requirements

- Python 3.9+
- FFmpeg and ffprobe installed and available on your PATH
- Dependencies installed in a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Command-line mode

Render an MP4 with configured defaults:

```bash
python src/main.py --videos-only --output-mode render --output Synced_video.mp4
```

Create only a Resolve EDL (no MP4 render):

```bash
python src/main.py --videos-only --output-mode resolve \
  --video1 path/to/camera1.mp4 --video2 path/to/camera2.mp4 \
  --resolve-edl podpy_resolve.edl
```

Create both outputs:

```bash
python src/main.py --videos-only --output-mode both \
  --video1 path/to/camera1.mp4 --video2 path/to/camera2.mp4 \
  --output Synced_video.mp4 --resolve-edl podpy_resolve.edl
```

Use `--audio1` and `--audio2` instead of `--videos-only` to provide separate audio. Both videos need audio with at least 30 seconds of shared material for reliable sync estimation.

## Notes

The EDL uses CMX 3600 non-drop-frame timecode at the configured 30 fps, includes original clip names and source paths as comments, and intentionally omits audio so the audio mix can be arranged in Resolve. The cut list JSON is also written. Camera 1 defines the timeline duration; clips are referenced rather than transcoded in timeline-only mode.

FFmpeg/ffprobe are still used for audio extraction and analysis in timeline-only mode, but no rendered video file is encoded.
