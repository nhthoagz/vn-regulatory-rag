"""Pipeline trả lời: BM25 + fallback bản gốc + render trích dẫn + guard (SPEC §7–§9)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.common.paths import INDEX_DIR
from src.core import tools
from src.core.guard import CITATION_RE, check_answer, numbers_in
from src.core.tools import CalcError
from src.retrieval.bm25 import BM25Index

ARTICLE_RE = re.compile(r"điều\s+(\d+[a-z]?)", re.I)
KIND_PATTERNS = (
    ("holiday", ("ngày lễ", "ngày nghỉ lễ", "lễ, tết")),
    ("weekend", ("cuối tuần", "ngày nghỉ hằng tuần", "thứ bảy", "chủ nhật")),
    ("night", ("ban đêm", "ca đêm")),
    ("weekday", ("ngày thường", "ngày làm việc bình thường")),
)
SENTENCE_END = re.compile(r"(?<=[.;:])\s+")
MAX_QUOTE_CHARS = 420
DEFAULT_THRESHOLD = 1.5
DEFAULT_COVERAGE = 0.5
REFUSAL_TEXT = (
    "Không tìm thấy căn cứ trong phạm vi hai văn bản Bộ luật Lao động đang được index. "
    "Tôi không trả lời ngoài phạm vi này."
)
MONEY_STRICT_RE = re.compile(
    r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>triệu|tr|nghìn|ngan)?\s*(?:đồng|đ\b|vnd)",
    re.I,
)
MONEY_UNIT_RE = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>triệu|tr)\b", re.I)
HOURS_RE = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?:giờ|tiếng)", re.I)
YEARS_RE = re.compile(r"(?P<num>\d+)\s*năm", re.I)


@dataclass
class Answer:
    """Kết quả một lượt hỏi, đủ để chấm điểm và để API trả về."""

    question: str
    intent: str
    answer: str
    citations: list[str] = field(default_factory=list)
    node_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    tool_output: dict | None = None
    violations: list[str] = field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    needs_input: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "intent": self.intent,
            "answer": self.answer,
            "citations": self.citations,
            "node_ids": self.node_ids,
            "warnings": self.warnings,
            "tool_output": self.tool_output,
            "violations": self.violations,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "needs_input": self.needs_input,
        }


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def first_quote(text: str) -> str:
    """Câu đầu tiên đủ dài của chunk, cắt theo giới hạn ký tự."""
    for sentence in SENTENCE_END.split(text):
        candidate = sentence.strip()
        if len(candidate) >= 40:
            return candidate[:MAX_QUOTE_CHARS].strip()
    return text.strip()[:MAX_QUOTE_CHARS].strip()


def detect_intent(question: str) -> str:
    """Nhận diện ý định; chỉ vào nhánh tính khi câu hỏi có đủ tham số số học.

    Câu hỏi quy định ("Điều 98 quy định mức lương làm thêm giờ thế nào?") phải đi nhánh QA,
    không bị coi là bài toán tính thiếu dữ liệu.
    """
    lowered = question.lower()
    has_money = bool(MONEY_STRICT_RE.search(question) or MONEY_UNIT_RE.search(question))
    has_hours = bool(HOURS_RE.search(question))
    if ("làm thêm" in lowered or "tăng ca" in lowered) and (has_money or has_hours):
        return "calc_overtime"
    if (
        "nghỉ hằng năm" in lowered or "phép năm" in lowered or "ngày phép" in lowered
    ) and YEARS_RE.search(question):
        return "calc_leave"
    return "qa"


class Pipeline:
    """Nạp chunk/node/rule một lần rồi trả lời bằng trích dẫn nguyên văn."""

    def __init__(
        self,
        *,
        chunks_path: Path,
        nodes_path: Path,
        fallback_path: Path,
        default_doc_id: str = "18-VBHN-VPQH-2026",
        threshold: float = DEFAULT_THRESHOLD,
        coverage_threshold: float = DEFAULT_COVERAGE,
        mode: str = "bm25",
        dense_model: str | None = None,
    ) -> None:
        self.chunks = load_jsonl(chunks_path)
        self.nodes = {node["node_id"]: node for node in load_jsonl(nodes_path)}
        self.fallback = json.loads(fallback_path.read_text(encoding="utf-8"))
        self.rules = tools.load_rules()
        self.default_doc_id = default_doc_id
        self.threshold = threshold
        self.coverage_threshold = coverage_threshold
        self.index = BM25Index().fit([chunk["text"] for chunk in self.chunks])
        self.mode = mode
        self.hybrid = self._build_hybrid(mode, dense_model)

    def _build_hybrid(self, mode: str, dense_model: str | None):
        """Chỉ dựng HybridRetriever khi cần; thiếu numpy/model thì báo lỗi rõ ràng."""
        if mode == "bm25":
            return None
        import hashlib

        from src.retrieval.dense import DenseIndex
        from src.retrieval.hybrid import HybridRetriever

        chunk_sha = hashlib.sha256(
            "".join(chunk["text"] for chunk in self.chunks).encode("utf-8")
        ).hexdigest()
        dense = DenseIndex.build(
            texts=[chunk["text"] for chunk in self.chunks],
            chunk_ids=[chunk["node_id"] for chunk in self.chunks],
            model_key=(dense_model or "bge-m3"),
            chunk_sha=chunk_sha,
            cache_dir=INDEX_DIR,
        )
        return HybridRetriever(bm25=self.index, dense=dense, mode=mode)

    def _candidates(self, question: str, top_k: int) -> tuple[list[dict], list[str], str | None]:
        """Ứng viên cho câu hỏi, có boost theo Điều và fallback khi văn bản mặc định thiếu Điều."""
        article_match = ARTICLE_RE.search(question)
        if not article_match:
            hits = self.index.search(question, top_k=top_k)
            return [self.chunks[hit.index] for hit in hits], [], None

        number = article_match.group(1)
        entry = self.fallback.get(self.default_doc_id, {}).get(number)
        if entry:
            fallback_doc = entry["fallback_doc_id"]
            fallback_chunks = [
                chunk
                for chunk in self.chunks
                if chunk["doc_id"] == fallback_doc and chunk["article"] == number
            ]
            return fallback_chunks[:top_k], [entry["warning"]], number

        # Lọc theo Điều trên toàn bộ chunk (không chỉ top-30) rồi mới chấm điểm.
        indices = [
            index
            for index, chunk in enumerate(self.chunks)
            if chunk["article"] == number and chunk["doc_id"] == self.default_doc_id
        ]
        ranked = sorted(
            ((self.index.score_doc(question, index), index) for index in indices), reverse=True
        )
        boosted = [self.chunks[index] for score, index in ranked[:top_k] if score > 0]
        if boosted:
            return boosted, [], number
        hits = self.index.search(question, top_k=top_k)
        return [self.chunks[hit.index] for hit in hits], [], number

    @staticmethod
    def _allowed_numbers(chunks: list[dict], question: str) -> set[str]:
        allowed: set[str] = set()
        for chunk in chunks:
            allowed |= numbers_in(chunk["text"])
        return allowed | numbers_in(question)

    def render(self, markup: str) -> str:
        """Đổi `[[node_id]]` thành nhãn trích dẫn đọc được."""
        by_id = {chunk["node_id"]: chunk["citation"] for chunk in self.chunks}

        def replace(match: re.Match[str]) -> str:
            return by_id.get(match.group("node_id"), match.group("node_id"))

        return CITATION_RE.sub(replace, markup)

    def ask(self, question: str, top_k: int = 5) -> Answer:
        """Trả lời một câu hỏi; định tuyến theo intent rồi tới QA/calc."""
        intent = detect_intent(question)
        if intent == "calc_overtime":
            return self._calc_overtime(question)
        if intent == "calc_leave":
            return self._calc_leave(question)
        return self._qa(question, top_k)

    def _qa(self, question: str, top_k: int) -> Answer:
        chunks, warnings, article = self._candidates(question, top_k)
        if not chunks:
            return Answer(
                question, "qa", REFUSAL_TEXT, refused=True, refusal_reason="khong_co_can_cu"
            )

        best_hit = self.index.search(question, top_k=1)
        if article is None:
            if not best_hit or best_hit[0].score < self.threshold:
                return Answer(
                    question, "qa", REFUSAL_TEXT, refused=True, refusal_reason="diem_thap"
                )
            coverage = self.index.idf_coverage(question, best_hit[0].index)
            if coverage < self.coverage_threshold:
                return Answer(
                    question, "qa", REFUSAL_TEXT, refused=True, refusal_reason="ngoai_pham_vi"
                )

        best = chunks[0]
        markup = f'"{first_quote(best["text"])}" [[{best["node_id"]}]]'
        extra = chunks[1:4]
        if extra:
            markup += "\nXem thêm: " + ", ".join(f"[[{chunk['node_id']}]]" for chunk in extra)

        warning = warnings[0] if warnings else None
        node_ids = [chunk["node_id"] for chunk in chunks]
        checked = markup + (f"\n{warning}" if warning else "")
        allowed = self._allowed_numbers(chunks, question)
        if warning:
            allowed |= numbers_in(warning)
        violations = check_answer(
            checked,
            allowed_node_ids=node_ids,
            allowed_numbers=allowed,
            required_warning=warning,
        )
        if violations:
            safe = " ".join(f"[[{node_id}]]" for node_id in node_ids[:3])
            text = f"Không trích nguyên văn được an toàn; nguồn liên quan: {self.render(safe)}"
            if warning:
                text += f"\n{warning}"
            return Answer(
                question,
                "qa",
                text,
                node_ids=node_ids[:3],
                warnings=warnings,
                retrieved=chunks,
                violations=violations,
            )

        answer = self.render(checked)
        return Answer(
            question,
            "qa",
            answer,
            citations=[chunk["citation"] for chunk in chunks],
            node_ids=node_ids,
            warnings=warnings,
            retrieved=chunks,
        )

    def _calc_overtime(self, question: str) -> Answer:
        lowered = question.lower()
        kind = next(
            (name for name, words in KIND_PATTERNS if any(word in lowered for word in words)),
            None,
        )
        wage = self._money(question)
        hours = self._hours(question)
        missing = [
            name
            for name, value in (("loai_ngay", kind), ("luong_gio", wage), ("so_gio", hours))
            if value is None
        ]
        if missing:
            return Answer(
                question,
                "calc_overtime",
                "Thiếu dữ liệu để tính: " + ", ".join(missing),
                needs_input=missing,
            )
        try:
            result = tools.overtime(Decimal(str(wage)), Decimal(str(hours)), str(kind), self.rules)
        except CalcError as error:
            return Answer(
                question, "calc_overtime", f"Không tính được: {error}", needs_input=["du_lieu"]
            )

        rule = self.rules[result.rule_key]
        amount = int(result.amount)
        hours_text = f"{hours:g}"
        markup = (
            f"Tiền làm thêm giờ = lương giờ {int(wage)} × {result.rate_percent}% × {hours_text} giờ"
            f' = {amount} đồng. Căn cứ [[{rule["source_node_id"]}]]: "{rule["evidence"]}"'
        )
        chunk = next(
            (item for item in self.chunks if item["node_id"] == rule["source_node_id"]), None
        )
        allowed_numbers = self._allowed_numbers([chunk] if chunk else [], question) | {
            str(amount),
            str(result.rate_percent),
        }
        violations = check_answer(
            markup,
            allowed_node_ids=[rule["source_node_id"]],
            allowed_numbers=allowed_numbers,
        )
        answer = self.render(markup) if not violations else f"Kết quả tính: {amount} đồng"
        return Answer(
            question,
            "calc_overtime",
            answer,
            citations=[chunk["citation"]] if chunk else [],
            node_ids=[rule["source_node_id"]],
            retrieved=[chunk] if chunk else [],
            tool_output={"amount": amount, "rate_percent": result.rate_percent},
            violations=violations,
        )

    def _calc_leave(self, question: str) -> Answer:
        years = self._years(question)
        base_rule = self.rules.get("annual_leave_base")
        if years is None:
            return Answer(
                question,
                "calc_leave",
                "Thiếu dữ liệu để tính: so_nam_lam_viec",
                needs_input=["so_nam_lam_viec"],
            )
        if base_rule is None:
            return Answer(
                question, "calc_leave", "Thiếu rule annual_leave_base", needs_input=["rules"]
            )
        days, node_id = tools.annual_leave_days(int(base_rule["value"]), years, self.rules)
        evidence = self.rules["annual_leave_seniority_step"]["evidence"]
        markup = f'Số ngày nghỉ hằng năm: {days} ngày. Căn cứ [[{node_id}]]: "{evidence}"'
        chunk = next((item for item in self.chunks if item["node_id"] == node_id), None)
        allowed = self._allowed_numbers([chunk] if chunk else [], question) | {str(days)}
        violations = check_answer(
            markup, allowed_node_ids=[node_id], allowed_numbers=allowed
        )
        answer = self.render(markup) if not violations else f"Số ngày nghỉ hằng năm: {days} ngày"
        return Answer(
            question,
            "calc_leave",
            answer,
            citations=[chunk["citation"]] if chunk else [],
            node_ids=[node_id],
            retrieved=[chunk] if chunk else [],
            tool_output={"days": days},
            violations=violations,
        )

    @staticmethod
    def _money(question: str) -> int | None:
        """Lương giờ: '50.000 đồng', '50k' không hỗ trợ để tránh đoán sai đơn vị."""
        match = MONEY_STRICT_RE.search(question) or MONEY_UNIT_RE.search(question)
        if not match:
            return None
        try:
            return int(tools.parse_money(match.group(0)))
        except CalcError:
            return None

    @staticmethod
    def _hours(question: str) -> float | None:
        match = HOURS_RE.search(question)
        return float(match.group("num").replace(",", ".")) if match else None

    @staticmethod
    def _years(question: str) -> int | None:
        match = YEARS_RE.search(question)
        return int(match.group("num")) if match else None