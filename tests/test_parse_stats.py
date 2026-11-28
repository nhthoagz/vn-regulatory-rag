from __future__ import annotations

from scripts.parse_stats import summarize
from src.common.config import DocumentMeta
from src.ingest.loader import PageAnomaly
from src.ingest.parser import ParseIssue, ParseResult


def test_summarize_reports_missing_articles_and_issue_counts() -> None:
    doc = DocumentMeta(doc_id="T-2026", file="t.pdf", role="original")
    result = ParseResult(
        doc_id="T-2026",
        issues=[ParseIssue(kind="article_number_gap", message="thiếu Điều [7]", page=3)],
        stats={"article": 2},
        missing_articles=(7,),
    )
    summary = summarize(doc, result, pdf="data/raw/t-ocr.pdf", pdf_sha256="0" * 64, pages=5)
    assert summary["missing_articles"] == [7]
    assert summary["node_id_unique"] is True
    assert summary["issues"] == [
        {"kind": "article_number_gap", "severity": "warning", "count": 1}
    ]
    assert summary["errors"] == []
    assert summary["stats"] == {"article": 2}
    assert summary["scan_page_anomalies"] == []


def test_summarize_serializes_scan_page_anomalies() -> None:
    doc = DocumentMeta(doc_id="T-2026", file="t.pdf", role="consolidated")
    anomaly = PageAnomaly(
        kind="missing_printed_pages",
        pdf_pages=(32, 33),
        printed_numbers=(32, 35),
        detail="thiếu trang in [33, 34] trong bản scan",
    )
    summary = summarize(
        doc,
        ParseResult(doc_id="T-2026"),
        pdf="x",
        pdf_sha256="0" * 64,
        pages=2,
        anomalies=(anomaly,),
    )
    assert summary["scan_page_anomalies"] == [
        {
            "kind": "missing_printed_pages",
            "pdf_pages": [32, 33],
            "printed_numbers": [32, 35],
            "detail": "thiếu trang in [33, 34] trong bản scan",
        }
    ]


def test_summarize_surfaces_errors() -> None:
    doc = DocumentMeta(doc_id="T-2026", file="t.pdf", role="consolidated")
    result = ParseResult(
        doc_id="T-2026",
        issues=[ParseIssue(kind="article_without_chapter", message="m", page=1, severity="error")],
    )
    summary = summarize(doc, result, pdf="x", pdf_sha256="0" * 64, pages=1)
    assert summary["errors"][0]["kind"] == "article_without_chapter"