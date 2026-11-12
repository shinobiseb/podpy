from config import AUDIO1, AUDIO2, CUTS_JSON, OUTPUT, VIDEO, VIDEO2
from pipeline import process_project


def main():
    process_project(
        video1=VIDEO,
        video2=VIDEO2,
        audio1=AUDIO1,
        audio2=AUDIO2,
        output=OUTPUT,
        cuts_json=CUTS_JSON,
    )


if __name__ == "__main__":
    main()
