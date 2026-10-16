#!/usr/bin/env python3
"""Download the pinned MedCalc-Bench Verified release with checksums."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import urllib.request
from pathlib import Path

from prepare_case_library import DEFAULT_TEMPLATE, prepare_case_library

VERSION = "v1.0.7"
BASE_URL = (
    "https://raw.githubusercontent.com/nikhilk7153/"
    f"MedCalc-Bench-Verified/{VERSION}/datasets"
)
FILES = {
    "train_data.csv": "aeb0e9d7f4af403d759dd979f536e8b58ff2cc78a37ec1647fac2604d788568d",
    "test_data.csv": "91d222234a5a427de1127e864a199a51af9e709357352423c8a22857476e7abf",
    "one_shot_data.csv": "b7bda09583d95fdd5a1be2f6f08be9b57290c26694a6af21988d0a16ac9453c9",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(destination: Path, force: bool = False) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        target = destination / name
        if target.exists() and not force and sha256(target) == expected:
            print(f"[ok] {name} already present")
            continue

        part = destination / f"{name}.part"
        if part.exists():
            part.unlink()
        print(f"[download] {BASE_URL}/{name}")
        try:
            urllib.request.urlretrieve(f"{BASE_URL}/{name}", part)
            actual = sha256(part)
            if actual != expected:
                raise RuntimeError(
                    f"checksum mismatch for {name}: expected {expected}, got {actual}"
                )
            os.replace(part, target)
        finally:
            if part.exists():
                part.unlink()
        print(f"[ok] {name} sha256={expected}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path("data/processed"),
        help="download directory (default: data/processed)",
    )
    parser.add_argument("--force", action="store_true", help="replace valid existing files")
    parser.add_argument(
        "--skip-case-library",
        action="store_true",
        help="download only; do not hydrate the local few-shot case library",
    )
    args = parser.parse_args()
    try:
        destination = args.destination.resolve()
        download(destination, force=args.force)
        if not args.skip_case_library:
            count = prepare_case_library(
                DEFAULT_TEMPLATE,
                destination / "train_data.csv",
                destination / "case_library_merged_v1_8.json",
            )
            print(f"[ok] hydrated {count} few-shot entries")
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
