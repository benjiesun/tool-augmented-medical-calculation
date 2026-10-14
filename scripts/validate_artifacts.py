#!/usr/bin/env python3
"""Fail-fast checks for repository integrity and accidental disclosure."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".env",
    ".example",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SKIP_DIRS = {".git", ".venv", "__pycache__", "build", "dist"}
SECRET_PATTERNS = {
    "OpenAI-style secret": re.compile(
        r"(?<![A-Za-z])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}"
    ),
    "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
LOCAL_PATH_PATTERNS = {
    "Windows user path": re.compile(
        r"(?i)(?<![A-Za-z0-9])[A-Z]:[\\/](?:Users|Documents and Settings)[\\/]"
    ),
    "Unix user path": re.compile(r"(?<![A-Za-z0-9])/(?:home|Users)/[^/\s]+/"),
    "private storage mount": re.compile(
        r"(?<![A-Za-z0-9])/(?:data_[^/\s]+|mnt/[^/\s]+)/"
    ),
}


def iter_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and not any(part in SKIP_DIRS for part in path.parts):
            yield path


def validate_python(errors: list[str]) -> None:
    for path in iter_files():
        if path.suffix != ".py":
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f"invalid Python: {path.relative_to(ROOT)}: {exc}")


def validate_json(errors: list[str]) -> None:
    for path in iter_files():
        try:
            if path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
            elif path.suffix == ".jsonl":
                for line_number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    if line.strip():
                        json.loads(line)
        except (json.JSONDecodeError, UnicodeError) as exc:
            errors.append(f"invalid JSON: {path.relative_to(ROOT)}: {exc}")


def validate_calculators(errors: list[str]) -> None:
    tool_dir = ROOT / "artifacts" / "calculators" / "gpt_5_5"
    tools = sorted(tool_dir.glob("calculator_*.py"))
    ids = []
    for path in tools:
        match = re.match(r"calculator_(\d+)", path.stem)
        if match:
            ids.append(match.group(1))
    if len(tools) != 55 or len(set(ids)) != 55:
        errors.append(
            f"expected 55 unique calculator tools, found {len(tools)} files/"
            f"{len(set(ids))} IDs"
        )
    manifest_path = tool_dir / "SHA256SUMS"
    manifest = {}
    try:
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            digest, filename = line.split(None, 1)
            manifest[filename.strip()] = digest.lower()
    except (OSError, ValueError) as exc:
        errors.append(f"invalid calculator checksum manifest: {exc}")
        return

    if set(manifest) != {path.name for path in tools}:
        errors.append("calculator checksum manifest does not match tool files")
        return
    for path in tools:
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if manifest[path.name] != actual:
            errors.append(f"calculator checksum mismatch: {path.name}")


def validate_disclosure(errors: list[str]) -> None:
    for path in iter_files():
        relative = path.relative_to(ROOT)
        if path.name == "runtime.env":
            errors.append(f"secret-bearing runtime file present: {relative}")
        if path.stat().st_size > 50 * 1024 * 1024:
            errors.append(f"file exceeds 50 MiB: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 5 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{label} pattern in {relative}")
        for label, pattern in LOCAL_PATH_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{label} in {relative}")


def validate_note_free_templates(errors: list[str]) -> None:
    def visit(value, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else key
                if key == "patient_note" and str(child or "").strip():
                    errors.append(f"patient note committed in {relative}:{child_path}")
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    for template in ROOT.glob("data/processed/case_library_template*.json"):
        relative = template.relative_to(ROOT)
        try:
            visit(json.loads(template.read_text(encoding="utf-8")), "")
        except (json.JSONDecodeError, UnicodeError) as exc:
            errors.append(f"invalid case-library template: {relative}: {exc}")


def validate_manuscript_figure(errors: list[str]) -> None:
    image_path = ROOT / "assets" / "figure1.png"
    provenance_path = ROOT / "assets" / "figure1.source.json"
    try:
        metadata = json.loads(provenance_path.read_text(encoding="utf-8"))
        data = image_path.read_bytes()
        if metadata.get("image_file") != image_path.name:
            errors.append("figure provenance names a different image")
        if hashlib.sha256(data).hexdigest() != metadata.get("image_sha256"):
            errors.append("manuscript Figure 1 checksum mismatch")
        if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            errors.append("manuscript Figure 1 is not a PNG")
            return
        width, height = struct.unpack(">II", data[16:24])
        if (width, height) != (metadata.get("width"), metadata.get("height")):
            errors.append("manuscript Figure 1 dimensions do not match provenance")
    except (OSError, ValueError, struct.error, KeyError, TypeError) as exc:
        errors.append(f"invalid manuscript figure or provenance: {exc}")


def main() -> None:
    errors: list[str] = []
    validate_python(errors)
    validate_json(errors)
    validate_calculators(errors)
    validate_disclosure(errors)
    validate_note_free_templates(errors)
    validate_manuscript_figure(errors)
    if errors:
        for error in errors:
            print(f"[error] {error}", file=sys.stderr)
        raise SystemExit(1)
    print("[ok] Python and JSON syntax")
    print("[ok] 55 unique calculator tools and matching SHA-256 manifest")
    print("[ok] original manuscript Figure 1 checksum and dimensions")
    print("[ok] no common secrets, local user paths, committed notes, or files over 50 MiB")


if __name__ == "__main__":
    main()
