# CP3 — Hybrid retrieval (dense + fusion)

- Ngày chốt: 2026-11-28
- Artifact: `results/retrieval_ablation.json`, sha256
  `071cc65497126e77bdd6c89da510b5d5194d8a709e14eff76bba8d38aac13758`
- Model: `BAAI/bge-m3` và `intfloat/multilingual-e5-large`, embed CPU (`EMBED_THREADS=4`),
  cache theo `sha256(chunks_leaf.jsonl)` = `973e4ab6c318…`, `max_seq_length=512`.
- Tập đo: 180 câu `qa_eval` (loại trừ 20 câu OOS), tầng chunk `leaf` (1603 chunk).

## 1. Kết quả

| Hệ | P@5 | R@10 | nDCG@10 | MRR@10 | Δ MRR vs BM25 |
|---|---|---|---|---|---|
| BM25 | 0.1389 | 0.2554 | 0.2161 | 0.2615 | — |
| bge-m3 dense | 0.1078 | 0.1786 | 0.1498 | 0.2328 | -11.0% |
| bge-m3 linear | 0.1378 | 0.2647 | 0.2205 | 0.3230 | +23.5% |
| bge-m3 rrf | 0.1067 | 0.1964 | 0.1727 | 0.2726 | +4.2% |
| e5-large dense | 0.1022 | 0.1890 | 0.1574 | 0.2393 | -8.5% |
| **e5-large linear** | **0.1522** | **0.2879** | **0.2334** | **0.3273** | **+25.2%** |
| e5-large rrf | 0.1356 | 0.2103 | 0.1980 | 0.3152 | +20.5% |

## 2. Kết luận và giới hạn

- Chọn **e5-large + linear (alpha=0.5)** làm cấu hình hybrid: P@5 +9.6%, R@10 +12.7%, nDCG@10 +8.0%,
  MRR@10 +25.2% so BM25. Serving đã kiểm `mode=bm25|linear` qua API (200, 0 vi phạm guard).
- Dense **đơn lẻ** kém BM25: câu hỏi trong bộ đề chứa số Điều, BM25 khớp từ khoá chính xác; đây là
  kết quả thật trên corpus nhỏ 2 văn bản, không nên tổng quát hoá.
- Chưa tune `alpha`, chưa thêm reranker cross-encoder (~1.1 GB model), chưa thử `rrf` với trọng số.
- Đây là mức "hybrid chạy được + có số", chưa phải mức tối ưu.

## 3. Điều kiện còn treo

Human review bộ đề (CP3 theo PLAN §5) chưa thực hiện — số liệu ở trên là trên bộ đề máy sinh.
