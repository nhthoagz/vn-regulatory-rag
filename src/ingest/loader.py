"""Đọc PDF đã OCR thành các dòng có toạ độ và bỏ header/footer lặp lại.

Chỉ đọc `*-ocr.pdf` (bản có text layer), không đọc PDF gốc và không đọc file sidecar:
một nguồn sự thật duy nhất cho cả text và toạ độ.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

PAGE_NUMBER_RE = re.compile(r"^\s*(?:trang\s*)?\d{1,3}\s*$", re.IGNORECASE)
DIGIT_RE = re.compile(r"\d+")
SPACE_RE = re.compile(r"\s+")

DEFAULT_HEADER_FRAC = 0.10
DEFAULT_FOOTER_FRAC = 0.08
DEFAULT_MIN_PAGE_RATIO = 0.30


@dataclass(frozen=True, slots=True)
class Line:
    text: str
    page: int
    top: float
    bottom: float
    size: float
    bold: bool


@dataclass(frozen=True, slots=True)
class Page:
    number: int
    width: float
    height: float
    lines: tuple[Line, ...]


@dataclass(frozen=True, slots=True)
class PageAnomaly:
    """Bất thường thứ tự hoặc đánh số trang in phát hiện khi đọc bản scan."""

    kind: str
    pdf_pages: tuple[int, ...]
    printed_numbers: tuple[int | None, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class LoadResult:
    pdf: Path
    pages: tuple[Page, ...]
    lines_total: int
    lines_dropped: int
    dropped_texts: tuple[str, ...]
    page_order: tuple[int, ...] = ()
    anomalies: tuple[PageAnomaly, ...] = ()


def normalize_running_text(text: str) -> str:
    """Chuẩn hóa text để so sánh dòng lặp: bỏ số trang, gộp khoảng trắng."""
    collapsed = SPACE_RE.sub(" ", text).strip().lower()
    return DIGIT_RE.sub("#", collapsed)


def is_page_number(text: str) -> bool:
    return bool(PAGE_NUMBER_RE.match(text))


def extract_pages(pdf_path: Path) -> list[Page]:
    """Đọc toàn bộ trang, giữ thứ tự dòng theo toạ độ."""
    pages: list[Page] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            raw_lines = page.extract_text_lines(return_chars=True)
            lines: list[Line] = []
            for raw in raw_lines:
                text = (raw.get("text") or "").strip()
                if not text:
                    continue
                chars = raw.get("chars") or []
                sizes = [float(ch.get("size", 0.0)) for ch in chars]
                fonts = [str(ch.get("fontname", "")) for ch in chars]
                lines.append(
                    Line(
                        text=text,
                        page=page.page_number,
                        top=float(raw.get("top", 0.0)),
                        bottom=float(raw.get("bottom", 0.0)),
                        size=max(sizes) if sizes else 0.0,
                        bold=any("bold" in font.lower() for font in fonts),
                    )
                )
            pages.append(
                Page(
                    number=page.page_number,
                    width=float(page.width),
                    height=float(page.height),
                    lines=tuple(lines),
                )
            )
    return pages

def _band_lines(page: Page, frac: float, from_top: bool) -> list[Line]:
    limit = page.height * frac
    if from_top:
        return [line for line in page.lines if line.bottom <= limit]
    return [line for line in page.lines if line.top >= page.height - limit]


def strip_running_heads(
    pages: list[Page],
    header_frac: float = DEFAULT_HEADER_FRAC,
    footer_frac: float = DEFAULT_FOOTER_FRAC,
    min_page_ratio: float = DEFAULT_MIN_PAGE_RATIO,
) -> LoadResult:
    """Bỏ dòng header/footer lặp lại ở nhiều trang và dòng chỉ có số trang.

    Không bỏ dòng nội dung: chỉ bỏ khi dòng nằm trong dải đầu/cuối trang **và**
    xuất hiện ở >= max(3, min_page_ratio * số trang) trang khác nhau.
    """
    if not pages:
        return LoadResult(pdf=Path(""), pages=(), lines_total=0, lines_dropped=0, dropped_texts=())

    threshold = max(3, int(len(pages) * min_page_ratio))
    counters: dict[str, int] = {}
    for page in pages:
        seen: set[str] = set()
        for line in _band_lines(page, header_frac, True) + _band_lines(page, footer_frac, False):
            key = normalize_running_text(line.text)
            if key and key not in seen:
                seen.add(key)
                counters[key] = counters.get(key, 0) + 1

    running = {key for key, count in counters.items() if count >= threshold}
    dropped_texts: list[str] = []
    kept_pages: list[Page] = []
    lines_total = 0
    lines_dropped = 0

    for page in pages:
        kept: list[Line] = []
        for line in page.lines:
            lines_total += 1
            in_top_band = line.bottom <= page.height * header_frac
            in_bottom_band = line.top >= page.height - page.height * footer_frac
            key = normalize_running_text(line.text)
            removable = (in_top_band or in_bottom_band) and (
                key in running or is_page_number(line.text)
            )
            if removable:
                lines_dropped += 1
                if line.text not in dropped_texts:
                    dropped_texts.append(line.text)
                continue
            kept.append(line)
        kept_pages.append(Page(page.number, page.width, page.height, tuple(kept)))

    return LoadResult(
        pdf=Path(""),
        pages=tuple(kept_pages),
        lines_total=lines_total,
        lines_dropped=lines_dropped,
        dropped_texts=tuple(dropped_texts[:50]),
    )


def _numbers_with_top(lines: list[Line]) -> list[tuple[float, int]]:
    pairs: list[tuple[float, int]] = []
    for line in lines:
        match = DIGIT_RE.search(line.text)
        if match:
            pairs.append((float(line.top), int(match.group())))
    return pairs


def detect_printed_number(
    page: Page,
    header_frac: float = DEFAULT_HEADER_FRAC,
    footer_frac: float = DEFAULT_FOOTER_FRAC,
) -> int | None:
    """Số trang **in** ở dải đáy (ưu tiên) hoặc dải đỉnh; bỏ qua số trong nội dung."""
    footer = _numbers_with_top(
        [line for line in _band_lines(page, footer_frac, False) if is_page_number(line.text)]
    )
    if footer:
        return max(footer)[1]
    header = _numbers_with_top(
        [line for line in _band_lines(page, header_frac, True) if is_page_number(line.text)]
    )
    if header:
        return min(header)[1]
    return None


def reorder_by_printed_numbers(pages: list[Page]) -> tuple[list[Page], list[PageAnomaly]]:
    """Sắp lại các trang bị đảo thứ tự trong bản scan và ghi lại bất thường.

    Chỉ đảo khi hai trang liền nhau có số trang in ngược nhau đúng 1 đơn vị và các trang
    xung quanh vẫn tăng, để không sửa nhầm khi OCR đọc sai số trang. Trang không đọc được
    số thì bỏ qua, không đoán.
    """
    if len(pages) < 2:
        return pages, []

    printed = [detect_printed_number(page) for page in pages]
    order = list(range(len(pages)))
    anomalies: list[PageAnomaly] = []

    for index in range(len(order) - 1):
        left = printed[order[index]]
        right = printed[order[index + 1]]
        if left is None or right is None or left != right + 1:
            continue
        before = printed[order[index - 1]] if index > 0 else None
        after = printed[order[index + 2]] if index + 2 < len(order) else None
        if before is not None and before >= right:
            continue
        if after is not None and after <= left:
            continue
        order[index], order[index + 1] = order[index + 1], order[index]
        anomalies.append(
            PageAnomaly(
                kind="swapped_printed_pages",
                pdf_pages=(pages[order[index]].number, pages[order[index + 1]].number),
                printed_numbers=(printed[order[index]], printed[order[index + 1]]),
                detail="hai trang bị đảo thứ tự trong bản scan; đã sắp lại theo số trang in",
            )
        )

    reordered = [pages[index] for index in order]
    numbers = [printed[index] for index in order]
    for index in range(len(numbers) - 1):
        first, second = numbers[index], numbers[index + 1]
        if first is None or second is None:
            continue
        gap = second - first
        if gap == 1:
            continue
        pair = (reordered[index].number, reordered[index + 1].number)
        if 1 < gap <= 3:
            missing = list(range(first + 1, second))
            anomalies.append(
                PageAnomaly(
                    kind="missing_printed_pages",
                    pdf_pages=pair,
                    printed_numbers=(first, second),
                    detail=f"thiếu trang in {missing} trong bản scan",
                )
            )
        else:
            anomalies.append(
                PageAnomaly(
                    kind="printed_number_jump_unexplained",
                    pdf_pages=pair,
                    printed_numbers=(first, second),
                    detail=f"số trang in nhảy từ {first} sang {second}; nghi OCR đọc sai số trang",
                )
            )
    return reordered, anomalies


def load_pages(
    pdf_path: Path,
    header_frac: float = DEFAULT_HEADER_FRAC,
    footer_frac: float = DEFAULT_FOOTER_FRAC,
    min_page_ratio: float = DEFAULT_MIN_PAGE_RATIO,
) -> LoadResult:
    """Đọc PDF và bỏ header/footer, trả kèm số liệu để ghi vào report."""
    pages = extract_pages(pdf_path)
    pages, anomalies = reorder_by_printed_numbers(pages)
    result = strip_running_heads(pages, header_frac, footer_frac, min_page_ratio)
    return LoadResult(
        pdf=pdf_path,
        pages=result.pages,
        lines_total=result.lines_total,
        lines_dropped=result.lines_dropped,
        dropped_texts=result.dropped_texts,
        page_order=tuple(page.number for page in result.pages),
        anomalies=tuple(anomalies),
    )