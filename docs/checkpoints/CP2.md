# CP2 — Retrieval + trả lời + guard (nhánh BM25)

- Ngày chốt: 2026-11-28
- Artifact: `results/eval_report.json`, sha256
  `f8555d42b97f1aa1488c09e81bd518a4fdfa232edb00bc26dd820359d8268414`
- Ablation: `results/header_ablation.json`, sha256
  `09fa6a1a35cf7c811bb723fda0830c6f495895c309f17971cec88b1dd19382d7`
- Bộ đề: `eval/qa_eval.jsonl` (200 câu) + `eval/calc_eval.jsonl` (30 case), sinh bằng mẫu tất định
  `template_v1`. **Chưa có human review** — điều kiện của CP3.

## 1. Trả lời (split `all`)

| Loại | Số câu | Độ chính xác |
|---|---|---|
| `article_lookup` | 120 | 1.00 |
| `clause_lookup` | 40 | 1.00 |
| `fallback_article` (Điều 76–79 → bản gốc + cảnh báo) | 20 | 1.00 |
| `oos` (ngoài phạm vi → từ chối) | 20 | 0.95 |
| `calc_*` (làm thêm giờ, nghỉ hằng năm) | 30 | 30/30 |
| Vi phạm guard | — | 1 |

Tách tập: dev `oos 0.9167`, calc 18/18 (`results/eval_dev.json`); test `oos 1.00`, calc 12/12
(`results/eval_test.json`). Ngưỡng từ chối IDF-coverage `0.85`, chọn trên dev.

## 2. Retrieval BM25 theo tầng chunk

| Tầng | P@5 | nDCG@10 | MRR@10 |
|---|---|---|---|
| leaf | 0.1389 | 0.2161 | 0.2615 |
| clause | 0.1689 | 0.2539 | 0.2971 |
| article | 0.0767 | 0.3138 | 0.2614 |

Cách đọc: gold của câu "Điều N quy định gì?" là **toàn bộ node lá của Điều N**, nên P@5/Recall mức node
bị phạt nặng; chất lượng trả lời thật đo bằng `gold_cited` = 1.00 ở bảng §1.

## 3. Ablation header trích dẫn (BM25)

| Header | P@5 | nDCG@10 | MRR@10 |
|---|---|---|---|
| `true` | 0.1389 | 0.2161 | 0.2615 |
| `none` | 0.0044 | 0.0045 | 0.0074 |
| `placebo` | 0.0056 | 0.0069 | 0.0110 |

Cảnh báo diễn giải: phần lớn chênh lệch đến từ việc câu hỏi có chứa "Điều N" nên khớp header;
kết quả này chứng minh header giúp khớp **số Điều**, không chứng minh giúp hiểu ngữ nghĩa.

## 4. Kết luận

**PASS** cho nhánh BM25/extractive. Nhánh hybrid (dense + fusion) đã đo xong và tốt hơn BM25 —
xem `docs/checkpoints/CP3-hybrid.md`.
