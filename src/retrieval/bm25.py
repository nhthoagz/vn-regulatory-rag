"""BM25 thuần Python trên chunk tiếng Việt (SPEC §7, thay cho `bm25s` khi chưa cài).

Chỉ dùng thư viện chuẩn để pipeline chạy được offline, không tải model. Nếu sau này cài
`bm25s` thì `retrieve()` có thể đổi backend mà không đổi interface.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

TOKEN_RE = re.compile(r"[\w%]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Tách token mức âm tiết; giữ `%` và số để bắt được '150%', '200 giờ'."""
    return TOKEN_RE.findall(text.lower())


@dataclass(frozen=True, slots=True)
class Hit:
    index: int
    score: float


class BM25Index:
    """BM25 Okapi với tham số mặc định k1=1.5, b=0.75."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.doc_tokens: list[list[str]] = []
        self.doc_len: list[int] = []
        self.avgdl = 0.0
        self.term_freqs: list[Counter[str]] = []
        self.idf: dict[str, float] = {}

    def fit(self, documents: Iterable[str]) -> BM25Index:
        self.doc_tokens = [tokenize(document) for document in documents]
        self.doc_len = [len(tokens) for tokens in self.doc_tokens]
        self.term_freqs = [Counter(tokens) for tokens in self.doc_tokens]
        total = sum(self.doc_len)
        self.avgdl = total / len(self.doc_len) if self.doc_len else 0.0
        doc_freq: Counter[str] = Counter()
        for freqs in self.term_freqs:
            doc_freq.update(freqs.keys())
        count = len(self.doc_tokens)
        self.idf = {
            term: math.log(1 + (count - freq + 0.5) / (freq + 0.5))
            for term, freq in doc_freq.items()
        }
        return self

    def score_doc(self, query: str, doc_index: int) -> float:
        """Điểm BM25 của một chunk cụ thể, dùng cho boost theo Điều."""
        terms = tokenize(query)
        freqs = self.term_freqs[doc_index]
        length = self.doc_len[doc_index]
        denominator_norm = self.k1 * (1 - self.b + self.b * length / (self.avgdl or 1.0))
        score = 0.0
        for term in terms:
            freq = freqs.get(term)
            if not freq:
                continue
            score += self.idf.get(term, 0.0) * (freq * (self.k1 + 1)) / (freq + denominator_norm)
        return score

    def idf_coverage(self, query: str, doc_index: int) -> float:
        """Tỷ lệ khối lượng IDF của query được chunk phủ; dùng để quyết định từ chối."""
        terms = list(dict.fromkeys(tokenize(query)))
        total = sum(self.idf.get(term, 0.0) for term in terms)
        if not total:
            return 0.0
        matched = sum(
            self.idf.get(term, 0.0) for term in terms if term in self.term_freqs[doc_index]
        )
        return matched / total

    def search(self, query: str, top_k: int = 10) -> list[Hit]:
        if not tokenize(query) or not self.doc_tokens:
            return []
        scores = [self.score_doc(query, index) for index in range(len(self.doc_tokens))]
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results: list[Hit] = []
        for index in ranked[:top_k]:
            if scores[index] > 0:
                results.append(Hit(index=index, score=scores[index]))
        return results