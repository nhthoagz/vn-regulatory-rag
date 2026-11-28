"""Số La Mã cho tên Chương, kèm bước OCR lại cục bộ để sửa lỗi nhận dạng.

OCR toàn trang đọc sai số La Mã (`l`, `H`, `VH`, `XIHI`) — xem CP-T00b-ocr.md.
Vì vậy dòng tiêu đề Chương được cắt ra và OCR lại bằng psm 7 với whitelist chữ La Mã;
chỉ khi đó mới chấp nhận giá trị. Không suy đoán theo thứ tự.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

import pdfplumber

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
ROMAN_ORDER = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]

WHITELIST = "IVXLCDM"


def parse_roman(token: str) -> int | None:
    """Đọc số La Mã chuẩn; trả None nếu token không phải số La Mã hợp lệ.

    Chỉ chấp nhận chữ HOA: OCR ra 'l' (chữ L thường) không được hiểu thành 50.
    """
    text = token.strip().strip(" .,:;-–—")
    if not text or any(ch not in ROMAN_VALUES for ch in text):
        return None
    total = 0
    previous = 0
    for ch in reversed(text):
        value = ROMAN_VALUES[ch]
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    if to_roman(total) != text:
        return None
    return total


def to_roman(value: int) -> str:
    if value < 1 or value > 3999:
        raise ValueError(f"số La Mã ngoài phạm vi: {value}")
    parts: list[str] = []
    remaining = value
    for number, symbol in ROMAN_ORDER:
        while remaining >= number:
            parts.append(symbol)
            remaining -= number
    return "".join(parts)


def _crop_to_png(
    page: pdfplumber.page.Page,
    bbox: tuple[float, float, float, float],
    dpi: int,
) -> Path:
    image = page.crop(bbox).to_image(resolution=dpi)
    handle = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    path = Path(handle.name)
    handle.close()
    image.original.save(path)
    return path


def ocr_roman_region(
    page: pdfplumber.page.Page,
    bbox: tuple[float, float, float, float],
    dpi: int = 300,
) -> str | None:
    """OCR lại đúng vùng ảnh của dòng tiêu đề với whitelist chữ La Mã."""
    png = _crop_to_png(page, bbox, dpi)
    try:
        result = subprocess.run(
            [
                "tesseract",
                str(png),
                "stdout",
                "--psm",
                "7",
                "-c",
                f"tessedit_char_whitelist={WHITELIST}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        cleaned = result.stdout.strip().replace(" ", "").replace("\n", "")
        return cleaned or None
    finally:
        png.unlink(missing_ok=True)


def make_roman_fixer(
    pdf_path: Path,
    dpi: int = 300,
) -> Callable[[int, tuple[float, float, float, float]], str | None]:
    """Tạo hàm sửa số La Mã cho một PDF; giữ PDF mở cho tất cả các lần gọi."""

    def fixer(page_number: int, bbox: tuple[float, float, float, float]) -> str | None:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_number - 1]
            return ocr_roman_region(page, bbox, dpi)

    return fixer