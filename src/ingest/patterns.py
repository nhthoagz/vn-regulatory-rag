"""Regex nhận dạng cấu trúc văn bản quy phạm (SPEC §6.3) và has_exception (§6.5)."""

from __future__ import annotations

import re

# OCR đọc sai số La Mã thành nhiều dạng: "VỊ" (VI), "VH" (VII), "XIHI" (XIII), "l" (I).
# Vì vậy token sau chữ "Chương" chỉ được chứa các ký tự này; nhờ đó "Chương trình an toàn"
# (một dòng nội dung Điều) không bị nhận nhầm là tiêu đề chương.
ROMANISH = "IVXLCDMHIl1|ỊÌÍÎĨỈ"

CHAPTER_RE = re.compile(rf"^Chương\s+(?P<num>[{ROMANISH}]+)\s*$")
CHAPTER_WITH_TITLE_RE = re.compile(rf"^Chương\s+(?P<num>[{ROMANISH}]+)\s+(?P<title>\S.*)$")

SECTION_RE = re.compile(r"^Mục\s+(?P<num>\d+)\s*$")
SECTION_WITH_TITLE_RE = re.compile(r"^Mục\s+(?P<num>\d+)\s+(?P<title>\S.*)$")

# "Điều" phải đúng chữ hoa; cho phép ký tự rác ở đầu dòng (OCR sinh ra
# "_ Điều 28.", "“Điều 37.", ". Điều 68."). Dấu gạch dưới phải loại riêng vì "_"
# thuộc \w nên [^\w] không nuốt được nó. Chữ "Điều" chấp nhận các biến thể đọc
# sai: sai dấu thanh (Điêu/Điểu/Điếu/Điệu) và nhầm u/n (Điền). Dùng escape
# Unicode để tránh lỗi gõ nhầm dấu thanh.
ARTICLE_RE = re.compile(
    r"^[^\w_]*?[\u0110\u00D0][iI][\u00EAe\u1EBF\u1EC1\u1EC3\u1EC5\u1EC7][un]\s+"
    r"(?P<num>\d+[a-zđ]?)\.\s*(?P<rest>\S.*)?$"
)

# Số Điều đứng sau một dấu chấm, dùng cho tiêu đề bị OCR phá nát chữ.
# Ví dụ thật: "- Đi2ềÀ u 219. Sử2 a đôÄi» , bồ Ä sung ..." -> số 219 còn đọc được.
_NUMBER_DOT_RE = re.compile(r"(?<![\d])(?P<num>\d{1,3}[a-zđ]?)\.\s+(?P<rest>\S.*)$")

# Khoản: "1." hoặc "1," (lỗi OCR hệ thống đã đo ở CP-T00b), giới hạn 1-3 chữ số để
# không bắt nhầm số tiền kiểu "1.000.000".
CLAUSE_RE = re.compile(r"^(?P<num>\d{1,3})[.,]\s+(?P<rest>\S.*)$")

# Điểm: "a)" ... chỉ trong phạm vi một Khoản.
POINT_RE = re.compile(r"^(?P<ch>[abcdđeghiklmnopqrstuvxy])\)\s+(?P<rest>\S.*)$")

# Cắt phần sau nội dung: mục lục, nơi nhận, phụ lục.
CUT_RE = re.compile(r"^(MỤC\s*LỤC|NƠI\s*NHẬN|PHỤ\s*LỤC)\b", re.IGNORECASE)

EXCEPTION_RE = re.compile(
    r"ngoại trừ|trừ trường hợp|trừ khi|(?<!khấu )\btrừ\b|không áp dụng",
    re.IGNORECASE,
)

# Tiêu đề Chương/Mục thường viết hoa toàn bộ.
UPPER_TITLE_RE = re.compile(r"^[A-ZĐÐ0-9 ,.\-/()]+$")


def has_exception(text: str) -> bool:
    """True nếu đoạn text chứa mệnh đề loại trừ.

    "khấu trừ" (Điều 102) không tính là loại trừ; có test âm tính cho trường hợp này.
    """
    return bool(EXCEPTION_RE.search(text))


def is_upper_title(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 3:
        return False
    return bool(UPPER_TITLE_RE.match(stripped)) and any(ch.isalpha() for ch in stripped)


def match_chapter(text: str) -> tuple[str, str | None] | None:
    """Trả (token số La Mã, tiêu đề cùng dòng nếu có) hoặc None."""
    match = CHAPTER_WITH_TITLE_RE.match(text)
    if match:
        return match.group("num"), match.group("title").strip()
    match = CHAPTER_RE.match(text)
    if match:
        return match.group("num"), None
    return None


def match_section(text: str) -> tuple[int, str | None] | None:
    match = SECTION_WITH_TITLE_RE.match(text)
    if match:
        return int(match.group("num")), match.group("title").strip()
    match = SECTION_RE.match(text)
    if match:
        return int(match.group("num")), None
    return None


def match_article(text: str) -> tuple[str, str] | None:
    match = ARTICLE_RE.match(text)
    if not match:
        return None
    rest = (match.group("rest") or "").strip()
    return match.group("num"), rest


def match_article_heading_fallback(
    text: str, expected: tuple[int, str]
) -> tuple[str, str] | None:
    """Cứu tiêu đề Điều bị OCR phá chữ nhưng vẫn còn số Điều.

    Chỉ nhận khi số đọc được đúng bằng ``expected`` (số Điều kế tiếp mà bộ đếm
    đang chờ), phần đứng trước số là rác ngắn (<= 14 ký tự, có ký tự không phải
    chữ) và nội dung sau dấu chấm bắt đầu bằng chữ. Nhờ ràng buộc ``expected``
    nên không thể biến một dòng khoản/điểm ("2. Trường hợp ...") thành Điều.
    """
    if len(text) > 120:
        return None
    match = _NUMBER_DOT_RE.search(text)
    if not match:
        return None
    number = match.group("num")
    if article_key(number) != expected:
        return None
    prefix = text[: match.start("num")].strip()
    rest = match.group("rest").strip()
    if not prefix or len(prefix) > 14:
        return None
    if not any(not ch.isalpha() and not ch.isspace() for ch in prefix):
        return None
    if not rest[:1].isalpha():
        return None
    return number, rest


def match_clause(text: str) -> tuple[int, str] | None:
    match = CLAUSE_RE.match(text)
    if not match:
        return None
    return int(match.group("num")), match.group("rest").strip()


def match_point(text: str) -> tuple[str, str] | None:
    match = POINT_RE.match(text)
    if not match:
        return None
    return match.group("ch"), match.group("rest").strip()


def is_cut_marker(text: str) -> bool:
    return bool(CUT_RE.match(text.strip()))


def article_key(num: str) -> tuple[int, str]:
    """Khóa so sánh số Điều: "2" < "2a" < "3"."""
    if num and num[-1].isdigit():
        return int(num), ""
    return int(num[:-1]), num[-1]