"""Dựng cây node từ các dòng đã đọc (SPEC §6.3 – §6.5).

Bảng biểu được xử lý ở task riêng (T06) để parser này chỉ lo cấu trúc phân cấp.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from src.common.config import DocumentMeta
from src.common.ids import (
    Level,
    make_article_id,
    make_chapter_id,
    make_clause_id,
    make_point_id,
    make_section_id,
    parse_node_id,
)
from src.common.normalize import normalize_text
from src.common.schema import Node
from src.ingest.loader import Line, Page
from src.ingest.patterns import (
    article_key,
    has_exception,
    is_cut_marker,
    match_article,
    match_article_heading_fallback,
    match_chapter,
    match_clause,
    match_point,
    match_section,
)
from src.ingest.roman import parse_roman, to_roman

# Ngưỡng nhận diện "đã bước sang mục lục": gặp lại số Điều nhỏ sau khi đã đọc nhiều điều.
TOC_MIN_ARTICLES = 100
TOC_MAX_ARTICLE = 10

# Cửa sổ cho phép "đảo trang scan": Điều đứng sau Điều trước nhưng lệch không quá mức này.
# Đo được ở T05: bản hợp nhất in trang 16 trước trang 15 nên Điều 35 nằm sau Điều 36.
# Chỉ áp dụng cho số Điều **chưa từng** xuất hiện; số đã xuất hiện là văn bản lặp, phải giữ
# làm text, nếu không sẽ sinh node_id trùng. Bất biến: len(ids) == len(set(ids)).
LOCAL_DISORDER_WINDOW = 3


@dataclass
class ParseIssue:
    kind: str
    message: str
    page: int | None = None
    line: str | None = None
    severity: str = "warning"


@dataclass
class ParseResult:
    doc_id: str
    nodes: list[Node] = field(default_factory=list)
    issues: list[ParseIssue] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    missing_articles: tuple[int, ...] = ()


@dataclass
class _Rec:
    node_id: str
    level: Level
    parent_id: str | None
    article: str | None = None
    clause: int | None = None
    point: str | None = None
    page_first: int = 0
    page_last: int = 0
    texts: list[str] = field(default_factory=list)
    lead_in: str | None = None


class Builder:
    """Nhận từng dòng theo thứ tự tài liệu và dựng cây node."""

    def __init__(self, doc: DocumentMeta) -> None:
        self.doc = doc
        self.records: list[_Rec] = []
        self.by_id: dict[str, _Rec] = {}
        self.issues: list[ParseIssue] = []
        self.stats: Counter[str] = Counter()
        self.chapter: str | None = None
        self.chapter_index = 0
        self.section: int | None = None
        self.section_index = 0
        self.article: str | None = None
        self.clause: int | None = None
        self.point: str | None = None
        self.current_id: str | None = None
        self.last_article: tuple[int, str] | None = None
        self.seen_articles: set[int] = set()
        self.seen_article_keys: set[tuple[int, str]] = set()
        self.missing_articles: list[int] = []
        self.pending_gaps: list[tuple[list[int], int, int, Line]] = []
        self.point_letters: list[str] = []
        self.stopped = False

    # --- tiện ích -------------------------------------------------------

    def _issue(
        self,
        kind: str,
        message: str,
        line: Line,
        severity: str = "warning",
    ) -> None:
        self.issues.append(
            ParseIssue(
                kind=kind,
                message=message,
                page=line.page,
                line=line.text,
                severity=severity,
            )
        )

    def _add(
        self,
        node_id: str,
        level: Level,
        parent_id: str | None,
        page: int,
        *,
        article: str | None = None,
        clause: int | None = None,
        point: str | None = None,
    ) -> _Rec:
        record = _Rec(
            node_id=node_id,
            level=level,
            parent_id=parent_id,
            article=article,
            clause=clause,
            point=point,
            page_first=page,
            page_last=page,
        )
        self.records.append(record)
        self.by_id[node_id] = record
        self.current_id = node_id
        self.stats[level.value] += 1
        return record

    def _append_text(self, text: str, page: int) -> None:
        if self.current_id is None:
            self.stats["preamble_lines"] += 1
            return
        record = self.by_id[self.current_id]
        record.texts.append(text)
        record.page_last = page

    def _expected_article(self) -> tuple[int, str]:
        """Số Điều kế tiếp mà bộ đếm đang chờ, dùng cho fallback cứu tiêu đề."""
        if self.last_article is None:
            return (1, "")
        return (self.last_article[0] + 1, "")

    # --- vòng lặp chính -------------------------------------------------

    def feed(self, line: Line) -> None:
        """Xử lý một dòng theo thứ tự ưu tiên: marker cắt > Chương > Mục > Điều > Khoản > Điểm."""
        text = normalize_text(line.text)
        if self.stopped or not text:
            return

        if is_cut_marker(text):
            self.stopped = True
            self.stats["cut_marker"] += 1
            return

        chapter = match_chapter(text)
        if chapter is not None:
            self._open_chapter(chapter[0], chapter[1], line, text)
            return

        section = match_section(text)
        if section is not None:
            self._open_section(section[0], section[1], line, text)
            return

        article = match_article(text)
        if article is None:
            article = match_article_heading_fallback(text, self._expected_article())
            if article is not None:
                message = f"Điều {article[0]} cứu từ dòng bị OCR phá chữ: {text[:60]!r}"
                self._issue("article_heading_recovered", message, line)
        if article is not None:
            self._open_article(article[0], article[1], line, text)
            return

        if self.article is not None:
            clause = match_clause(text)
            if clause is not None:
                self._open_clause(clause[0], clause[1], line, text)
                return

            if self.clause is not None:
                point = match_point(text)
                if point is not None:
                    self._open_point(point[0], point[1], line, text)
                    return

        self._append_text(text, line.page)

# --- mở node --------------------------------------------------------

    def _open_chapter(self, token: str, title: str | None, line: Line, text: str) -> None:
        expected = self.chapter_index + 1
        self.chapter_index = expected
        roman = to_roman(expected)
        parsed = parse_roman(token)
        if parsed is None:
            message = f"Chương {token!r} không đọc được số La Mã; gán theo thứ tự {roman}"
            self._issue("chapter_token_unreadable", message, line)
        elif parsed != expected:
            message = f"Chương {token!r} đọc ra {parsed} nhưng theo thứ tự phải là {expected}"
            severity = "error" if abs(parsed - expected) > 1 else "warning"
            self._issue("chapter_sequence_mismatch", message, line, severity)

        self.chapter = roman
        self.section = None
        self.section_index = 0
        self.article = None
        self.clause = None
        self.point = None
        self.point_letters = []
        record = self._add(make_chapter_id(self.doc.doc_id, roman), Level.chapter, None, line.page)
        if title:
            record.texts.append(title)

    def _open_section(self, number: int, title: str | None, line: Line, text: str) -> None:
        if self.chapter is None:
            message = f"Mục {number} xuất hiện trước chương đầu tiên"
            self._issue("section_without_chapter", message, line, "error")
            self._append_text(text, line.page)
            return

        expected = self.section_index + 1
        if number != expected:
            message = f"Mục {number} không khớp thứ tự {expected} trong Chương {self.chapter}"
            self._issue("section_out_of_order", message, line)
        self.section_index = number
        self.section = number
        self.article = None
        self.clause = None
        self.point = None
        record = self._add(
            make_section_id(self.doc.doc_id, self.chapter, number),
            Level.section,
            make_chapter_id(self.doc.doc_id, self.chapter),
            line.page,
        )
        if title:
            record.texts.append(title)

    def _open_article(self, number: str, rest: str, line: Line, text: str) -> None:
        key = article_key(number)
        if self.last_article is not None and key <= self.last_article:
            if self.stats["article"] >= TOC_MIN_ARTICLES and key[0] <= TOC_MAX_ARTICLE:
                self.stopped = True
                count = self.stats["article"]
                message = f"gặp lại Điều {number} sau {count} điều: coi là bắt đầu mục lục"
                self._issue("content_cut", message, line)
                return
            # Đảo trang scan: số Điều giảm, chưa từng xuất hiện, lệch trong cửa sổ nhỏ.
            # Nếu số Điều đã xuất hiện (kể cả đúng bằng Điều trước) thì đây là văn bản lặp,
            # không được tạo node mới vì node_id sẽ trùng và `by_id` ghi đè node cũ.
            local_disorder = (
                key < self.last_article
                and key not in self.seen_article_keys
                and self.last_article[0] - key[0] <= LOCAL_DISORDER_WINDOW
            )
            if local_disorder:
                message = (
                    f"Điều {number} đứng sau Điều {self.last_article[0]} "
                    f"(lệch {self.last_article[0] - key[0]} điều): coi là đảo trang scan"
                )
                self._issue("article_local_disorder", message, line)
            else:
                message = f"Điều {number} không tăng so với Điều trước; giữ làm text"
                self._issue("article_out_of_order", message, line)
                self._append_text(text, line.page)
                return

        if self.chapter is None:
            message = f"Điều {number} xuất hiện trước chương đầu tiên"
            self._issue("article_without_chapter", message, line, "error")

        if (
            key[1] == ""
            and self.last_article is not None
            and key[0] > self.last_article[0] + 1
        ):
            missing = [
                value
                for value in range(self.last_article[0] + 1, key[0])
                if value not in self.seen_articles
            ]
            if missing:
                # Chốt ở resolve_gaps: đảo trang scan làm Điều 35 xuất hiện sau Điều 36,
                # lúc gặp 36 thì tưởng thiếu 35 nhưng cuối văn bản 35 vẫn có.
                self.pending_gaps.append(
                    (missing, self.last_article[0], key[0], line)
                )

        self.seen_articles.add(key[0])
        self.seen_article_keys.add(key)
        self.last_article = key
        self.article = number
        self.clause = None
        self.point = None
        self.point_letters = []
        record = self._add(
            make_article_id(self.doc.doc_id, number),
            Level.article,
            self._current_container(),
            line.page,
            article=number,
        )
        if rest:
            record.texts.append(rest)

    def _open_clause(self, number: int, rest: str, line: Line, text: str) -> None:
        expected = 1 if self.clause is None else self.clause + 1
        if number != expected:
            message = f"khoản {number} không khớp kỳ vọng {expected} trong Điều {self.article}"
            self._issue("clause_out_of_order", message, line)
            self._append_text(text, line.page)
            return

        article = self.article or ""
        self.clause = number
        self.point = None
        self.point_letters = []
        record = self._add(
            make_clause_id(self.doc.doc_id, article, number),
            Level.clause,
            make_article_id(self.doc.doc_id, article),
            line.page,
            article=self.article,
            clause=number,
        )
        if rest:
            record.texts.append(rest)

    def _open_point(self, letter: str, rest: str, line: Line, text: str) -> None:
        if letter in self.point_letters:
            message = f"điểm {letter}) lặp lại trong Điều {self.article} khoản {self.clause}"
            self._issue("point_duplicate", message, line)
            self._append_text(text, line.page)
            return

        article = self.article or ""
        clause = self.clause or 0
        clause_id = make_clause_id(self.doc.doc_id, article, clause)
        lead_in = " ".join(self.by_id[clause_id].texts).strip() or None
        self.point_letters.append(letter)
        self.point = letter
        record = self._add(
            make_point_id(self.doc.doc_id, article, clause, letter),
            Level.point,
            clause_id,
            line.page,
            article=self.article,
            clause=self.clause,
            point=letter,
        )
        record.lead_in = lead_in
        if rest:
            record.texts.append(rest)

# --- kết thúc -------------------------------------------------------

    def _current_container(self) -> str | None:
        if self.chapter is None:
            return None
        if self.section is not None:
            return make_section_id(self.doc.doc_id, self.chapter, self.section)
        return make_chapter_id(self.doc.doc_id, self.chapter)

    def _path_of(self, record: _Rec) -> list[str]:
        labels: list[str] = []
        current = record.parent_id
        while current is not None:
            parent = self.by_id[current]
            labels.append(_label(parent))
            current = parent.parent_id
        return list(reversed(labels))

    def finalize(self) -> list[Node]:
        children: dict[str, list[str]] = {}
        for record in self.records:
            if record.parent_id:
                children.setdefault(record.parent_id, []).append(record.node_id)

        nodes: list[Node] = []
        for record in self.records:
            text = " ".join(part for part in record.texts if part).strip()
            lead_in = record.lead_in
            nodes.append(
                Node(
                    node_id=record.node_id,
                    doc_id=self.doc.doc_id,
                    level=record.level,
                    path=self._path_of(record),
                    article=record.article,
                    clause=record.clause,
                    point=record.point,
                    text=text,
                    lead_in=lead_in,
                    parent_id=record.parent_id,
                    children=children.get(record.node_id, []),
                    has_exception=has_exception(text) or has_exception(lead_in or ""),
                    effective_from=self.doc.effective_from,
                    page_span=(record.page_first, record.page_last),
                )
            )
        return nodes

    def resolve_gaps(self) -> None:
        """Chốt danh sách Điều thiếu sau khi đã duyệt hết văn bản.

        Chỉ báo thiếu khi đến cuối vẫn không thấy Điều đó. Đảo trang scan (in trang 16
        trước trang 15 của bản hợp nhất) làm Điều 35 xuất hiện sau Điều 36, nên không
        được kết luận thiếu ngay tại chỗ.
        """
        for missing, previous, current, line in self.pending_gaps:
            unresolved = [value for value in missing if value not in self.seen_articles]
            if not unresolved:
                continue
            message = (
                f"thiếu Điều {unresolved} giữa Điều {previous} và Điều {current}"
                "; nhiều khả năng bản scan bị mất trang"
            )
            self._issue("article_number_gap", message, line)
            self.missing_articles.extend(unresolved)
        self.missing_articles = sorted(set(self.missing_articles))
        self.stats["article_gap_missing"] = len(self.missing_articles)

    def finalize_stats(self) -> dict[str, int]:
        return dict(self.stats)


def _label(record: _Rec) -> str:
    """Nhãn hiển thị của một cấp, dùng cho `path` và header của chunk."""
    parsed = parse_node_id(record.node_id)
    if parsed.level is Level.chapter:
        return f"Chương {parsed.chapter}"
    if parsed.level is Level.section:
        return f"Mục {parsed.section}"
    if parsed.level is Level.article:
        return f"Điều {parsed.article}"
    if parsed.level is Level.clause:
        return f"Khoản {parsed.clause}"
    if parsed.level is Level.point:
        return f"Điểm {parsed.point}"
    return "Bảng"


def parse_pages(pages: Iterable[Page], doc: DocumentMeta) -> ParseResult:
    """Chạy parser trên toàn bộ trang đã đọc, trả node + issue + số liệu."""
    builder = Builder(doc)
    for page in pages:
        for line in page.lines:
            builder.feed(line)
    builder.resolve_gaps()
    return ParseResult(
        doc_id=doc.doc_id,
        nodes=builder.finalize(),
        issues=builder.issues,
        stats=builder.finalize_stats(),
        missing_articles=tuple(builder.missing_articles),
    )