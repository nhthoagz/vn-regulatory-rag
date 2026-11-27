from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
MANIFEST = RAW_DIR / "SOURCES.md"

EXPECTED_FILES = {
    "blld2019-45-2019-qh14-goc.pdf",
    "blld2019-18-vbhn-vpqh-2026.pdf",
}

ROW_RE = re.compile(r"^\|\s*`([^`]+\.pdf)`\s*\|\s*`([0-9a-f]{64})`\s*\|")

pytestmark = pytest.mark.realdata


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        match = ROW_RE.match(line)
        if match:
            entries[match.group(1)] = match.group(2)
    return entries


def test_manifest_exposes_both_documents() -> None:
    assert set(manifest_entries()) == EXPECTED_FILES


def test_manifest_hashes_match_files_on_disk() -> None:
    entries = manifest_entries()
    missing = [name for name in entries if not (RAW_DIR / name).is_file()]
    if missing:
        pytest.skip(f"pdf files not present locally: {missing}")
    for name, expected in entries.items():
        assert sha256_of(RAW_DIR / name) == expected, name