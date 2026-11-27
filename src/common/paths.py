"""Đường dẫn chuẩn của repo, một nguồn duy nhất cho mọi module."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = REPO_ROOT / "config"
RULES_DIR = REPO_ROOT / "rules"
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INDEX_DIR = DATA_DIR / "index"
RESULTS_DIR = REPO_ROOT / "results"
EVAL_DIR = REPO_ROOT / "eval"
GOLDEN_DIR = EVAL_DIR / "golden"
DOCS_DIR = REPO_ROOT / "docs"
CHECKPOINTS_DIR = DOCS_DIR / "checkpoints"
LOGS_DIR = REPO_ROOT / "logs"