"""Ghép BM25 với dense bằng RRF hoặc linear (SPEC §7, mode `rrf`/`linear`).

Dùng cho ablation; `Pipeline` mặc định vẫn BM25 nên test/API không đổi hành vi.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.retrieval.bm25 import BM25Index

if TYPE_CHECKING:  # numpy/sentence-transformers là dependency tuỳ chọn, import lúc chạy
    from src.retrieval.dense import DenseIndex

RRF_K = 60


def _minmax(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    low, high = min(scores.values()), max(scores.values())
    span = high - low
    if span <= 0:
        return {index: 1.0 for index in scores}
    return {index: (value - low) / span for index, value in scores.items()}


def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: score(d) = Σ 1/(k + rank)."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking, start=1):
            scores[index] = scores.get(index, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def linear_fuse(
    bm25: dict[int, float], dense: dict[int, float], alpha: float = 0.5
) -> list[tuple[int, float]]:
    """alpha * dense_norm + (1 - alpha) * bm25_norm trên hợp các index."""
    bm = _minmax(bm25)
    dn = _minmax(dense)
    fused = {
        index: alpha * dn.get(index, 0.0) + (1 - alpha) * bm.get(index, 0.0)
        for index in set(bm) | set(dn)
    }
    return sorted(fused.items(), key=lambda item: item[1], reverse=True)


@dataclass
class HybridRetriever:
    """Truy xuất theo `mode`; `allow` giới hạn tập index được phép trả về."""

    bm25: BM25Index
    dense: DenseIndex | None = None
    mode: str = "bm25"
    alpha: float = 0.5

    def search(
        self, query: str, top_k: int = 10, allow: set[int] | None = None
    ) -> list[tuple[int, float]]:
        if self.mode == "dense":
            if self.dense is None:
                raise ValueError("mode=dense nhưng chưa build dense index")
            hits = self.dense.search(query, top_k=top_k * 20)
            return [(i, s) for i, s in hits if allow is None or i in allow][:top_k]

        bm25_scores = {
            index: score
            for index, score in (
                (i, self.bm25.score_doc(query, i)) for i in range(self.bm25.doc_count)
            )
            if score > 0 and (allow is None or index in allow)
        }
        if self.mode == "bm25" or self.dense is None:
            return sorted(bm25_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]

        dense_hits = dict(self.dense.search(query, top_k=top_k * 20))
        if allow is not None:
            dense_hits = {i: s for i, s in dense_hits.items() if i in allow}
        if self.mode == "linear":
            return linear_fuse(bm25_scores, dense_hits, self.alpha)[:top_k]
        bm25_rank = [i for i, _ in sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)]
        dense_rank = [i for i, _ in sorted(dense_hits.items(), key=lambda x: x[1], reverse=True)]
        return rrf_fuse([bm25_rank, dense_rank])[:top_k]
