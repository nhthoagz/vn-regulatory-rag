from __future__ import annotations

from pathlib import Path

import pytest

from src.common.config import DocumentMeta
from src.common.paths import RAW_DIR
from src.ingest.loader import Line, Page, load_pages
from src.ingest.parser import ParseResult, parse_pages

DOC = DocumentMeta(doc_id="TEST-2026", file="test.pdf", role="consolidated")


def make_pages(texts: list[str]) -> list[Page]:
    lines = tuple(
        Line(
            text=text,
            page=1,
            top=20.0 + 15 * index,
            bottom=35.0 + 15 * index,
            size=10.0,
            bold=False,
        )
        for index, text in enumerate(texts)
    )
    return [Page(number=1, width=600.0, height=800.0, lines=lines)]


def parse(texts: list[str]) -> ParseResult:
    return parse_pages(make_pages(texts), DOC)


def nodes_by_id(result: ParseResult) -> dict[str, object]:
    return {node.node_id: node for node in result.nodes}


SAMPLE = [
    "Chương I",
    "NHỮNG QUY ĐỊNH CHUNG",
    "Điều 1. Phạm vi điều chỉnh",
    "Bộ luật này quy định quan hệ lao động.",
    "1. Người lao động",
    "a) làm việc theo hợp đồng lao động",
    "b) làm việc không có hợp đồng lao động",
    "2. Người sử dụng lao động, trừ trường hợp quy định tại khoản 3 Điều này.",
    "Chương II",
    "Điều 2. Đối tượng áp dụng",
    "Người lao động nước ngoài làm việc tại Việt Nam.",
    "MỤC LỤC",
    "Điều 1. Phạm vi điều chỉnh",
]


def test_hierarchy_ids_and_paths() -> None:
    nodes = nodes_by_id(parse(SAMPLE))
    for node_id in (
        "TEST-2026:CI",
        "TEST-2026:CII",
        "TEST-2026:D1",
        "TEST-2026:D1.K1",
        "TEST-2026:D1.K1.a",
    ):
        assert node_id in nodes

    point = nodes["TEST-2026:D1.K1.a"]
    assert point.path == ["Chương I", "Điều 1", "Khoản 1"]
    assert point.lead_in == "Người lao động"
    assert nodes["TEST-2026:D1"].path == ["Chương I"]


def test_chapter_title_is_attached_to_chapter_node() -> None:
    nodes = nodes_by_id(parse(SAMPLE))
    assert nodes["TEST-2026:CI"].text == "NHỮNG QUY ĐỊNH CHUNG"


def test_has_exception_on_clause_level() -> None:
    nodes = nodes_by_id(parse(SAMPLE))
    assert nodes["TEST-2026:D1.K2"].has_exception is True
    assert nodes["TEST-2026:D1.K1"].has_exception is False


def test_children_and_parents_are_consistent() -> None:
    nodes = nodes_by_id(parse(SAMPLE))
    article = nodes["TEST-2026:D1"]
    assert set(article.children) == {"TEST-2026:D1.K1", "TEST-2026:D1.K2"}
    clause = nodes["TEST-2026:D1.K1"]
    assert set(clause.children) == {"TEST-2026:D1.K1.a", "TEST-2026:D1.K1.b"}
    assert clause.parent_id == "TEST-2026:D1"
    assert nodes["TEST-2026:D1.K1.a"].parent_id == "TEST-2026:D1.K1"


def test_content_after_cut_marker_is_not_parsed() -> None:
    result = parse(SAMPLE)
    assert result.stats["article"] == 2
    assert result.stats["cut_marker"] == 1


def test_chapter_number_comes_from_order_not_from_ocr_token() -> None:
    result = parse(["Chương II", "Điều 1. Nội dung", "Chương VH", "Điều 2. Nội dung"])
    nodes = nodes_by_id(result)
    assert "TEST-2026:CI" in nodes
    assert "TEST-2026:CII" in nodes
    kinds = {issue.kind for issue in result.issues}
    assert "chapter_sequence_mismatch" in kinds
    assert "chapter_token_unreadable" in kinds


def test_misread_point_is_kept_as_text_not_a_new_clause() -> None:
    result = parse(
        ["Điều 1. Nội dung", "1. Người lao động", "a) điểm a", "3. điểm b bị OCR sai"]
    )
    nodes = nodes_by_id(result)
    assert "TEST-2026:D1.K1.a" in nodes
    assert not any(node_id.endswith(".K2") for node_id in nodes)
    assert "clause_out_of_order" in {issue.kind for issue in result.issues}
    assert "3. điểm b" in nodes["TEST-2026:D1.K1.a"].text


def test_repeated_article_is_kept_as_text() -> None:
    result = parse(["Điều 5. Nội dung", "Điều 5. Nhắc lại", "Điều 6. Nội dung"])
    assert result.stats["article"] == 2
    assert "article_out_of_order" in {issue.kind for issue in result.issues}


def test_section_before_chapter_is_an_error() -> None:
    result = parse(["Mục 1 Quy định chung"])
    assert "section_without_chapter" in {issue.kind for issue in result.issues}
    assert result.stats.get("chapter", 0) == 0


def test_parsing_is_deterministic() -> None:
    first = [node.node_id for node in parse(SAMPLE).nodes]
    second = [node.node_id for node in parse(SAMPLE).nodes]
    assert first == second


@pytest.mark.realdata
def test_parse_real_consolidated_pdf(ocr_pdfs, settings) -> None:
    pdf_path = next(path for path in ocr_pdfs if "vbhn" in path.name)
    doc = settings.docs.by_id("18-VBHN-VPQH-2026")
    result = parse_pages(load_pages(pdf_path).pages, doc)
    assert result.stats["chapter"] == 17
    assert result.stats["article"] >= 200
    assert result.stats["clause"] >= 400
    assert result.stats["point"] >= 100
    errors = [issue for issue in result.issues if issue.severity == "error"]
    assert not errors, [issue.message for issue in errors[:5]]


def test_repeated_article_does_not_duplicate_node_id() -> None:
    result = parse(["Điều 5. Nội dung", "Điều 5. Nhắc lại", "Điều 6. Nội dung"])
    ids = [node.node_id for node in result.nodes]
    assert len(ids) == len(set(ids))
    assert ids.count("TEST-2026:D5") == 1
    assert "article_out_of_order" in {issue.kind for issue in result.issues}


def test_page_swap_keeps_every_article_once() -> None:
    # Đảo trang scan thật (in trang 16 trước trang 15): Điều 35 nằm sau Điều 36.
    result = parse(["Điều 36. Nội dung 36", "Điều 35. Nội dung 35", "Điều 37. Nội dung 37"])
    ids = [node.node_id for node in result.nodes]
    assert {"TEST-2026:D35", "TEST-2026:D36", "TEST-2026:D37"} <= set(ids)
    assert len(ids) == len(set(ids))
    assert "article_local_disorder" in {issue.kind for issue in result.issues}
    assert result.missing_articles == ()


@pytest.mark.realdata
def test_parse_real_documents_have_expected_counts(settings) -> None:
    """Bản gốc phải đủ 220 Điều; bản hợp nhất thiếu đúng 4 Điều do mất trang scan."""
    expected = {
        "45-2019-QH14": (17, 220, ()),
        "18-VBHN-VPQH-2026": (17, 216, (76, 77, 78, 79)),
    }
    for doc_id, (chapters, articles, missing) in expected.items():
        doc = settings.docs.by_id(doc_id)
        pdf_path = RAW_DIR / f"{Path(doc.file).stem}-ocr.pdf"
        if not pdf_path.is_file():
            pytest.skip(f"thiếu {pdf_path.name}; chạy `make ocr` trước")
        result = parse_pages(load_pages(pdf_path).pages, doc)
        assert result.stats["chapter"] == chapters, doc_id
        assert result.stats["article"] == articles, doc_id
        assert result.missing_articles == missing, doc_id
        ids = [node.node_id for node in result.nodes]
        assert len(ids) == len(set(ids)), doc_id
        errors = [issue for issue in result.issues if issue.severity == "error"]
        assert not errors, (doc_id, [issue.message for issue in errors[:5]])