from __future__ import annotations

import math

import pytest

np = pytest.importorskip("numpy")

from src.retrieval.bm25 import BM25Index  # noqa: E402
from src.retrieval.hybrid import HybridRetriever, linear_fuse, rrf_fuse  # noqa: E402


class StubDense:
    """Dense giả: điểm cố định theo index, không cần model."""

    def __init__(self, scores: dict[int, float]) -> None:
        self._scores = scores

    def search(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        ranked = sorted(self._scores.items(), key=lambda item: item[1], reverse=True)
        return ranked[:top_k]


def test_rrf_prefers_documents_ranked_high_by_both() -> None:
    fused = dict(rrf_fuse([[0, 1, 2], [1, 0, 3]]))
    assert fused[0] > fused[2]
    assert fused[1] > fused[3]
    assert set(fused) == {0, 1, 2, 3}


def test_linear_fuse_normalises_each_signal() -> None:
    fused = dict(linear_fuse({0: 10.0, 1: 0.0}, {1: 0.9, 0: 0.1}, alpha=0.5))
    assert fused[0] == pytest.approx(0.5 * 0.0 + 0.5 * 1.0, abs=1e-6)
    assert fused[1] == pytest.approx(0.5 * 1.0 + 0.5 * 0.0, abs=1e-6)


def test_hybrid_bm25_mode_matches_bm25_index() -> None:
    texts = ["điều 98 làm thêm giờ", "điều 113 nghỉ hằng năm", "thuế doanh nghiệp"]
    bm25 = BM25Index().fit(texts)
    plain = [(hit.index, hit.score) for hit in bm25.search("điều 98", top_k=2)]
    hybrid = HybridRetriever(bm25=bm25, mode="bm25").search("điều 98", top_k=2)
    assert [index for index, _ in hybrid] == [index for index, _ in plain]


def test_hybrid_dense_mode_uses_dense_scores_and_allow_filter() -> None:
    texts = ["a", "b", "c"]
    bm25 = BM25Index().fit(texts)
    retriever = HybridRetriever(bm25=bm25, dense=StubDense({0: 0.1, 1: 0.9, 2: 0.5}), mode="dense")
    assert [i for i, _ in retriever.search("x", top_k=2)] == [1, 2]
    assert [i for i, _ in retriever.search("x", top_k=5, allow={0, 2})] == [2, 0]


def test_hybrid_rrf_merges_bm25_and_dense() -> None:
    texts = ["điều 98", "điều 113", "điều 98 làm thêm"]
    bm25 = BM25Index().fit(texts)
    retriever = HybridRetriever(
        bm25=bm25, dense=StubDense({0: 0.2, 1: 0.95, 2: 0.6}), mode="rrf"
    )
    ranked = [i for i, _ in retriever.search("điều 98", top_k=3)]
    assert ranked[0] in {0, 2}
    assert not math.isnan(ranked[0])