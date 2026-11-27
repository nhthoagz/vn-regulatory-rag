from __future__ import annotations

from scripts.check_leak import violations


def test_clean_list_has_no_violations() -> None:
    files = [
        "README.md",
        "SPEC.md",
        "src/common/ids.py",
        "data/raw/.gitkeep",
        "data/raw/SOURCES.md",
    ]
    assert violations(files) == []


def test_raw_pdf_is_a_violation() -> None:
    assert violations(["data/raw/blld2019-45-2019-qh14-ocr.pdf"]) == [
        "data/raw/blld2019-45-2019-qh14-ocr.pdf"
    ]


def test_index_and_processed_dirs_are_violations() -> None:
    files = ["data/index/dense/vectors.npy", "data/processed/nodes.jsonl"]
    assert violations(files) == files


def test_env_file_is_a_violation() -> None:
    assert violations([".env"]) == [".env"]
    assert violations(["config/.env"]) == ["config/.env"]


def test_env_example_is_allowed() -> None:
    assert violations([".env.example"]) == []