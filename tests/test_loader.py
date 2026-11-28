from __future__ import annotations

import pytest

from src.ingest.loader import (
    Line,
    Page,
    detect_printed_number,
    is_page_number,
    load_pages,
    normalize_running_text,
    reorder_by_printed_numbers,
    strip_running_heads,
)


def make_page(
    number: int,
    header: str = "",
    body: tuple[str, ...] = (),
    footer: str = "",
    height: float = 800.0,
) -> Page:
    """Trang giả lập: header ở đỉnh, nội dung ở giữa, footer ở đáy."""
    lines: list[Line] = []
    if header:
        lines.append(Line(text=header, page=number, top=30.0, bottom=45.0, size=10.0, bold=False))
    for index, text in enumerate(body):
        top = 300.0 + index * 20
        lines.append(Line(text=text, page=number, top=top, bottom=top + 15, size=10.0, bold=False))
    if footer:
        top = height - 40.0
        lines.append(
            Line(text=footer, page=number, top=top, bottom=top + 15, size=10.0, bold=False)
        )
    return Page(number=number, width=600.0, height=height, lines=tuple(lines))


def test_normalize_running_text_replaces_digits() -> None:
    assert normalize_running_text("Trang 12") == "trang #"
    assert normalize_running_text("Bộ luật Lao   động") == "bộ luật lao động"


def test_page_number_detection() -> None:
    assert is_page_number("12")
    assert is_page_number("Trang 7")
    assert not is_page_number("Điều 12")


def test_running_header_is_dropped_from_every_page() -> None:
    pages = [
        make_page(1, header="BỘ LUẬT LAO ĐỘNG 2019", body=("Điều 1. Phạm vi điều chỉnh",)),
        make_page(2, header="BỘ LUẬT LAO ĐỘNG 2019", body=("Điều 2. Đối tượng áp dụng",)),
        make_page(3, header="BỘ LUẬT LAO ĐỘNG 2019", body=("Điều 3. Giải thích từ ngữ",)),
    ]
    result = strip_running_heads(pages)
    assert result.lines_dropped == 3
    assert "BỘ LUẬT LAO ĐỘNG 2019" in result.dropped_texts
    for page in result.pages:
        assert all(line.text != "BỘ LUẬT LAO ĐỘNG 2019" for line in page.lines)
        assert page.lines


def test_body_lines_are_kept() -> None:
    pages = [make_page(number, body=("Điều 1. Nội dung",)) for number in (1, 2, 3)]
    result = strip_running_heads(pages)
    assert result.lines_dropped == 0
    assert all(page.lines for page in result.pages)


def test_page_numbers_in_footer_are_dropped() -> None:
    pages = [
        make_page(number, body=(f"Điều {number}. Nội dung",), footer=str(number))
        for number in (1, 2, 3)
    ]
    result = strip_running_heads(pages)
    kept_texts = [line.text for page in result.pages for line in page.lines]
    assert "1" not in kept_texts
    assert "Điều 1. Nội dung" in kept_texts
    assert result.lines_dropped == 3


def test_single_occurrence_in_band_is_not_dropped() -> None:
    # Một dòng chỉ xuất hiện ở 1 trang thì không thể coi là header chạy đầu trang.
    pages = [
        make_page(1, header="PHẦN THỨ NHẤT", body=("Điều 1. Nội dung",)),
        make_page(2, body=("Điều 2. Nội dung",)),
        make_page(3, body=("Điều 3. Nội dung",)),
    ]
    result = strip_running_heads(pages)
    assert result.lines_dropped == 0


def test_empty_input_is_safe() -> None:
    result = strip_running_heads([])
    assert result.pages == ()
    assert result.lines_total == 0


@pytest.mark.realdata
def test_load_pages_reads_ocr_pdf_without_running_heads(ocr_pdfs) -> None:
    pdf_path = ocr_pdfs[0]
    result = load_pages(pdf_path)
    assert result.pdf == pdf_path
    assert len(result.pages) > 10
    assert result.lines_total > 100
    assert result.lines_dropped < result.lines_total
    first = result.pages[0]
    assert first.lines
    assert all(line.page == 1 for line in first.lines)


def test_printed_number_is_read_from_footer() -> None:
    page = make_page(5, body=("Điều 5. Nội dung",), footer="5")
    assert detect_printed_number(page) == 5
    assert detect_printed_number(make_page(5, body=("Điều 5. Nội dung",))) is None
    # Số nằm trong nội dung không được coi là số trang in.
    assert detect_printed_number(make_page(5, body=("5",))) is None


def test_reorder_swaps_pages_with_reversed_printed_numbers() -> None:
    pages = [
        make_page(14, body=("Điều 34. Nội dung",), footer="14"),
        make_page(15, body=("Điều 36. Nội dung",), footer="16"),
        make_page(16, body=("Điều 35. Nội dung",), footer="15"),
        make_page(17, body=("Điều 37. Nội dung",), footer="17"),
    ]
    ordered, anomalies = reorder_by_printed_numbers(pages)
    assert [page.number for page in ordered] == [14, 16, 15, 17]
    assert [anomaly.kind for anomaly in anomalies] == ["swapped_printed_pages"]
    assert anomalies[0].printed_numbers == (15, 16)


def test_missing_printed_pages_are_reported() -> None:
    pages = [
        make_page(32, body=("Điều 75.",), footer="32"),
        make_page(33, body=("Điều 80.",), footer="35"),
    ]
    _, anomalies = reorder_by_printed_numbers(pages)
    assert [anomaly.kind for anomaly in anomalies] == ["missing_printed_pages"]
    assert anomalies[0].printed_numbers == (32, 35)
    assert anomalies[0].detail == "thiếu trang in [33, 34] trong bản scan"


def test_large_printed_number_jump_is_flagged_as_ocr_noise() -> None:
    pages = [make_page(21, footer="21"), make_page(22, footer="2")]
    _, anomalies = reorder_by_printed_numbers(pages)
    assert [anomaly.kind for anomaly in anomalies] == ["printed_number_jump_unexplained"]


@pytest.mark.realdata
def test_load_pages_reports_scan_page_anomalies(ocr_pdfs) -> None:
    vbhn = next(path for path in ocr_pdfs if "vbhn" in path.name)
    original = next(path for path in ocr_pdfs if "45-2019" in path.name)

    vbhn_result = load_pages(vbhn)
    kinds = [anomaly.kind for anomaly in vbhn_result.anomalies]
    assert "swapped_printed_pages" in kinds
    missing = next(a for a in vbhn_result.anomalies if a.kind == "missing_printed_pages")
    assert missing.printed_numbers == (32, 35)

    original_result = load_pages(original)
    assert not [
        anomaly
        for anomaly in original_result.anomalies
        if anomaly.kind == "missing_printed_pages"
    ]