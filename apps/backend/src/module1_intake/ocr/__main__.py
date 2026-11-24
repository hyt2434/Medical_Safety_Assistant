"""Run a local image through OCR without starting the API."""

import argparse

from module1_intake.ocr.application import LocalOcrService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to a printed prescription image")
    args = parser.parse_args()
    print(LocalOcrService().extract(args.image).model_dump_json(indent=2))


if __name__ == "__main__":
    main()
