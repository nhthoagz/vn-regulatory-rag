"""Fixture dùng chung.

Nguyên tắc: test cần dữ liệu thật thì `pytest.skip` kèm lý do rõ ràng,
không được pass im lặng khi thiếu dữ liệu.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.common.config import Settings, load_settings
from src.common.paths import PROCESSED_DIR, RAW_DIR, REPO_ROOT


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def settings() -> Settings:
    return load_settings()


@pytest.fixture(scope="session")
def raw_dir() -> Path:
    if not RAW_DIR.is_dir():
        pytest.skip("data/raw không tồn tại")
    return RAW_DIR


@pytest.fixture(scope="session")
def ocr_pdfs(raw_dir: Path) -> list[Path]:
    paths = sorted(raw_dir.glob("*-ocr.pdf"))
    if not paths:
        pytest.skip("chưa có *-ocr.pdf; chạy `make ocr` trước")
    return paths


@pytest.fixture(scope="session")
def nodes_file() -> Path:
    path = PROCESSED_DIR / "nodes.jsonl"
    if not path.is_file():
        pytest.skip("chưa có data/processed/nodes.jsonl; chạy `make ingest` trước")
    return path


@pytest.fixture(scope="session")
def nodes(nodes_file: Path) -> list[dict[str, object]]:
    with nodes_file.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]