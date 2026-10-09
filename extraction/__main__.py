"""CLI: python -m extraction [--processing-version extract-v3]."""
from __future__ import annotations

import argparse

from extraction.parse import PROCESSING_VERSION
from extraction.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract passages from bronze filing HTML")
    parser.add_argument("--processing-version", default=PROCESSING_VERSION)
    args = parser.parse_args()
    documents, passages, failures = run(args.processing_version)
    print(f"extracted {documents} documents, {passages} passages, "
          f"{failures} extraction failures (processing_version={args.processing_version})")


if __name__ == "__main__":
    main()
