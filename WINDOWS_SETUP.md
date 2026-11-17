# Windows setup and export notes

PodPy runs locally on Windows with Python 3, FFmpeg (including ffprobe), and the project dependencies. From PowerShell in the repository directory, run `setup_windows.bat` once and then `run_windows.bat`. The scripts use the repository's Windows virtual environment and check that FFmpeg and ffprobe are on `PATH`.

Place the four input files in `src\files`:

- `pov_seb.mp4` — reference camera video, with embedded audio
- `pov_gus.mp4` — second camera video, with embedded sync audio
- `pod1_seb.mp3` — first microphone track
- `pod1_gus.mp3` — second microphone track

The default outputs are written to the repository root: `Synced_video.mp4`, `test_synced_merged_cuts.json`, and `Synced_video.fcpxml`. The FCPXML timeline is generated from the same camera-cut sequence as the JSON and can be imported into Final Cut Pro. You can also use the cross-platform command-line setup described in `README.md`.
