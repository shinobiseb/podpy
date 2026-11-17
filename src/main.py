import argparse

from config import AUDIO1, AUDIO2, CUTS_JSON, OUTPUT, VIDEO, VIDEO2
from pipeline import process_project


def main():
    parser = argparse.ArgumentParser(
        description="Sync two camera videos, choose activity-driven cuts, and render an edit."
    )
    parser.add_argument("--video1", default=VIDEO, help="Reference/camera 1 video")
    parser.add_argument("--video2", default=VIDEO2, help="Camera 2 video")
    parser.add_argument("--audio1", default=AUDIO1, help="Separate audio track 1")
    parser.add_argument("--audio2", default=AUDIO2, help="Separate audio track 2")
    parser.add_argument(
        "--videos-only",
        action="store_true",
        help="Use audio embedded in each video; do not require separate audio files",
    )
    parser.add_argument("--output", default=OUTPUT, help="Rendered MP4 path")
    parser.add_argument("--cuts-json", default=CUTS_JSON, help="Camera cut-list JSON path")
    parser.add_argument("--final-cut-xml", help="Optional Final Cut Pro XML output path")
    args = parser.parse_args()

    process_project(
        video1=args.video1,
        video2=args.video2,
        audio1=None if args.videos_only else args.audio1,
        audio2=None if args.videos_only else args.audio2,
        output=args.output,
        cuts_json=args.cuts_json,
        final_cut_xml=args.final_cut_xml,
    )


if __name__ == "__main__":
    main()
