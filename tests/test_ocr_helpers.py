from __future__ import annotations

from scripts.ocr import MIN_CHARS, load_documents, quality


def test_quality_counts_pages_above_threshold() -> None:
    pages = ["x" * MIN_CHARS, "short", "  " + "y" * MIN_CHARS + "  "]
    ok, ratio = quality(pages)
    assert ok == 2
    assert ratio == 0.6667


def test_quality_of_empty_document() -> None:
    assert quality([]) == (0, 0.0)


def test_docs_config_lists_two_documents_with_identity_markers() -> None:
    documents = load_documents()
    assert [doc["doc_id"] for doc in documents] == ["18-VBHN-VPQH-2026", "45-2019-QH14"]
    assert all(doc["identity_marker"] for doc in documents)
    assert all(doc["file"].endswith(".pdf") for doc in documents)
    assert {doc["role"] for doc in documents} == {"consolidated", "original"}