from __future__ import annotations

import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_DIRS = [
    "config",
    "rules",
    "scripts",
    "src",
    "tests",
    "results",
    "logs",
    "data/raw",
    "eval/golden",
    "docs/checkpoints",
]

EXPECTED_PACKAGES = [
    "src",
    "src.common",
    "src.ingest",
    "src.retrieve",
    "src.guard",
    "src.agent",
    "src.tools",
    "src.evaluation",
]

EXPECTED_IGNORES = [
    ".env",
    "data/raw/*",
    "data/processed/",
    "data/index/",
    "*.pt",
    "*.onnx",
    "*.npy",
]


def test_expected_directories_exist() -> None:
    missing = [rel for rel in EXPECTED_DIRS if not (REPO_ROOT / rel).is_dir()]
    assert not missing, f"missing directories: {missing}"


def test_expected_packages_importable() -> None:
    for name in EXPECTED_PACKAGES:
        assert importlib.import_module(name) is not None, name


def test_gitignore_covers_data_and_secrets() -> None:
    lines = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    missing = [pattern for pattern in EXPECTED_IGNORES if pattern not in lines]
    assert not missing, f"missing .gitignore entries: {missing}"


def test_spec_and_plan_present() -> None:
    for name in ("SPEC.md", "PLAN.md"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        assert len(text) > 1000, f"{name} looks truncated"