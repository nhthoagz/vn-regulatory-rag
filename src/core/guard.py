"""Kiểm tra câu trả lời trước khi trả cho người dùng (SPEC §8).

Ba luật cứng, kiểm bằng code chứ không bằng lời hứa:
1. Mọi `[[node_id]]` trong câu trả lời phải nằm trong tập ứng viên đã truy xuất/đã dùng.
2. Mọi con số trong câu trả lời phải có trong chunk đã trích, trong output của tool, hoặc
   trong chính câu hỏi của người dùng.
3. Nếu có node từ văn bản fallback thì câu trả lời phải chứa câu cảnh báo tương ứng.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
CITATION_RE = re.compile(r"\[\[(?P<node_id>[^\]]+)\]\]")


def numbers_in(text: str) -> set[str]:
    """Tập số xuất hiện trong text, đã chuẩn hoá dấu phân cách."""
    return {match.group().replace(",", ".") for match in NUMBER_RE.finditer(text)}


def citations_in(text: str) -> set[str]:
    return {match.group("node_id") for match in CITATION_RE.finditer(text)}


def check_answer(
    text: str,
    *,
    allowed_node_ids: Iterable[str],
    allowed_numbers: Iterable[str],
    required_warning: str | None = None,
) -> list[str]:
    """Trả danh sách vi phạm; rỗng nghĩa là câu trả lời qua được guard."""
    violations: list[str] = []
    allowed_ids = set(allowed_node_ids)
    unknown = sorted(citations_in(text) - allowed_ids)
    if unknown:
        violations.append(f"citation_khong_hop_le: {unknown}")
    allowed = {item.replace(",", ".") for item in allowed_numbers}
    visible = CITATION_RE.sub(" ", text)
    extra = sorted(numbers_in(visible) - allowed)
    if extra:
        violations.append(f"so_khong_co_trong_nguon: {extra}")
    if required_warning and required_warning not in text:
        violations.append("thieu_canh_bao_fallback")
    return violations