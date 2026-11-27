"""Fail if git tracks raw law data, model weights, or secrets."""

from __future__ import annotations

import subprocess
import sys

FORBIDDEN_PREFIXES = ("data/processed/", "data/index/")
FORBIDDEN_SUFFIXES = (".pdf", ".pt", ".onnx", ".npy", ".safetensors")
ALLOWED_RAW = frozenset({"data/raw/.gitkeep", "data/raw/SOURCES.md"})


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return [line for line in result.stdout.splitlines() if line.strip()]


def violations(files: list[str]) -> list[str]:
    bad: list[str] = []
    for path in files:
        if path in ALLOWED_RAW:
            continue
        if path.endswith(".env") or "/.env" in path:
            bad.append(path)
        elif path.startswith(FORBIDDEN_PREFIXES):
            bad.append(path)
        elif path.startswith("data/raw/"):
            bad.append(path)
        elif path.endswith(FORBIDDEN_SUFFIXES):
            bad.append(path)
    return bad


def main() -> int:
    files = tracked_files()
    bad = violations(files)
    print(f"tracked files: {len(files)}")
    if bad:
        print("LEAK - do not push:")
        for path in bad:
            print(f"  {path}")
        return 1
    print("clean: no raw law data, model weights, or secrets tracked")
    return 0


if __name__ == "__main__":
    sys.exit(main())