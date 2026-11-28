# Báo cáo cuối — vn-regulatory-rag (CP1 → CP2)

Mọi con số dưới đây copy từ artifact trong `results/` và `data/`, kèm sha256 để kiểm lại.

## 1. Ingest

`results/parse_stats.json` — sha256 `0f9f161960d467f42b2f5c0b0076969b5d584310218a0d9c5b61105c55bcc84a`

| Văn bản | Trang | Chương | Điều | Khoản | Điểm | Node | Điều thiếu | Lỗi |
|---|---|---|---|---|---|---|---|---|
| `18-VBHN-VPQH-2026` (mặc định) | 86 | 17 | 216 | 595 | 253 | 1104 | `[76, 77, 78, 79]` | 0 |
| `45-2019-QH14` (bản gốc) | 83 | 17 | 220 | 585 | 228 | 1071 | — | 0 |

`data/ingest_report.json` — sha256 `afd899fa04dc838ebbcf5fa9362c9988ced2df6747f051d77f1a86a309378a84`

- Chunk 3 tầng: `leaf` 1603, `clause` 1257, `article` 436 (tổng hai văn bản).
- Bản hợp nhất thiếu 4 Điều vì bản scan **mất 2 trang in (33–34)**: số trang in nhảy 32 → 35 giữa
  pdf trang 32 và 33 (`scan_page_anomalies.missing_printed_pages`).
- Bản scan còn **đảo trang in 15/16** (`swapped_printed_pages`); loader sắp lại theo số trang in.
- `fallback_map.json` ánh xạ Điều 76–79 sang bản gốc kèm câu cảnh báo bắt buộc.
- Ngày hiệu lực từ câu trích: bản gốc 2021-01-01 (Điều 220), bản hợp nhất 2026-07-01
  (`effective_kind: derived_from_amending_law`).

## 2. Bộ đề và kết quả trả lời

`eval/qa_eval.jsonl` sha256 `f4d1d4a66558bcf6b11a16919af116c91a3f63b4e35dd7bcddbdbae7f57b1352`
(200 câu: 120 tra Điều, 40 tra Khoản, 20 Điều thiếu, 20 ngoài phạm vi)
`eval/calc_eval.jsonl` sha256 `306a0920f799b0004b4251d7dc5f5a415670a65baa7cbfa17617c1706df6ade9` (30 case)

Sinh bằng mẫu tất định (`generator: template_v1`). **Chưa được người dùng kiểm duyệt tay** (SPEC §11).

`results/eval_report.json` sha256 `f8555d42b97f1aa1488c09e81bd518a4fdfa232edb00bc26dd820359d8268414`

| Loại | Số câu | Độ chính xác |
|---|---|---|
| `article_lookup` | 120 | 1.00 |
| `clause_lookup` | 40 | 1.00 |
| `fallback_article` | 20 | 1.00 (trích bản gốc + cảnh báo) |
| `oos` | 20 | 0.95 |
| `calc_*` | 30 | 30/30 |
| Vi phạm guard | — | 1 |

Tách tập: `results/eval_dev.json` sha256 `c23db9bf4594d1fe217787a7c8981bcae924cb475a0e9211e47d82d3bf51368f`
(oos 0.9167, calc 18/18); `results/eval_test.json` sha256
`6b73c65c853a0741d4dd1183381ccf4baa65622ab283efaa6e3c4fecb282331a` (oos 1.00, calc 12/12).
Ngưỡng từ chối `coverage=0.85` chọn trên dev.

## 3. Ablation header trích dẫn (BM25, không cần model)

`results/header_ablation.json` sha256 `09fa6a1a35cf7c811bb723fda0830c6f495895c309f17971cec88b1dd19382d7`

| Header | P@5 | nDCG@10 | MRR@10 |
|---|---|---|---|
| `true` | 0.1389 | 0.2161 | 0.2615 |
| `none` | 0.0044 | 0.0045 | 0.0074 |
| `placebo` | 0.0056 | 0.0069 | 0.0110 |

Đọc số này cho đúng: (a) gold của câu "Điều N quy định gì?" là **toàn bộ node lá của Điều N** nên
Recall/P@5 mức node bị phạt; chất lượng trả lời thật đo ở `gold_cited` = 1.00. (b) Khoảng cách
true ≫ none/placebo phần lớn vì câu hỏi có chứa "Điều N" — header giúp khớp đúng số Điều; đây là
tác dụng thật của header nhưng không chứng minh header giúp hiểu ngữ nghĩa.

## 3b. Ablation retrieval đầy đủ: BM25 vs dense vs fusion (leaf, 180 câu)

`results/retrieval_ablation.json` (sha256 ở §7)

| Hệ | P@5 | R@10 | nDCG@10 | MRR@10 |
|---|---|---|---|---|
| BM25 | 0.1389 | 0.2554 | 0.2161 | 0.2615 |
| bge-m3 dense | 0.1078 | 0.1786 | 0.1498 | 0.2328 |
| bge-m3 linear | 0.1378 | 0.2647 | 0.2205 | 0.3230 |
| bge-m3 rrf | 0.1067 | 0.1964 | 0.1727 | 0.2726 |
| e5-large dense | 0.1022 | 0.1890 | 0.1574 | 0.2393 |
| **e5-large linear** | **0.1522** | **0.2879** | **0.2334** | **0.3273** |
| e5-large rrf | 0.1356 | 0.2103 | 0.1980 | 0.3152 |

Đọc số cho đúng:
- **Dense đơn lẻ kém BM25** trên corpus nhỏ, miền hẹp này — vì phần lớn câu hỏi chứa đúng số Điều
  ("Điều 98 …") và BM25 khớp từ khoá rất mạnh. Đây là kết quả thật, không phải lỗi cấu hình.
- **Fusion linear tốt nhất**: e5-large + BM25 = P@5 0.1522 (+9.6% so BM25), R@10 0.2879 (+12.7%),
  nDCG@10 0.2334 (+8.0%), MRR@10 0.3273 (+25.2%). RRF kém linear ở thiết lập này.
- Chưa có reranker; chưa tune `alpha` (đang 0.5) và chưa tune `max_seq_length` (512, `truncated`
  ghi trong report).
- Đã kiểm serving: `POST /ask` với `mode=bm25` và `mode=linear` đều trả 200, 5 node, 0 vi phạm guard.

## 4. Đã làm

- Ingest: pdfplumber, tách header/footer, sửa thứ tự trang, parse Chương/Mục/Điều/Khoản/Điểm,
  issue theo mức, chốt Điều thiếu ở cuối văn bản, `node_id` duy nhất 100%.
- Chunk 3 tầng + header (có `placebo`), sha256 tập chunk, cache key theo `chunk_sha`.
- `rules/*.yaml` sinh từ text, 13 rule (150/200/300%, 30/20%, 200/300/40 giờ, 12/14/16 ngày,
  +1 ngày/5 năm, khấu trừ 30%), mỗi rule có `evidence` nguyên văn và test `evidence ⊂ node text`.
- Retrieval BM25 thuần Python, lọc theo Điều, từ chối bằng IDF coverage; guard 3 luật; API FastAPI
  (`/health`, `/ask`, `/calc/overtime`, `/calc/leave`); eval harness; Dockerfile; CI.

## 5. Chưa làm (lý do thật, không tô hồng)

- **Dense**: ĐÃ làm (bge-m3 + multilingual-e5-large, cache theo `chunk_sha`, embed CPU) + fusion
  `linear`/`rrf`; số ở §3b. **Reranker cross-encoder**: chưa (thêm ~1.1 GB model, chưa có ngân sách).
- **LLM viết câu trả lời**: client OpenAI-compatible đã có (`src/core/llm.py`, 4 test) nhưng **chưa bật**
  vì `sudo` cần mật khẩu để cài Ollama → không cài phi tương tác được. Câu trả lời hiện là trích nguyên văn.
- **Gradio UI** (§10): có scaffold `src/ui/gradio_app.py` (import lazy), chưa cài `gradio` nên chưa chạy.
- Chưa làm: mở rộng cross-reference, bảng calibration OOS đầy đủ (mới quét ngưỡng trên dev), tune
  `alpha`/rerank, human review bộ đề.
- Docker/CI mới ở mức file, **chưa chạy thật** (docker chưa cài trên máy).

## 6. Tái tạo

```bash
make ocr      # nếu chưa có *-ocr.pdf (đã chạy: 86/86 và 83/83 trang đạt)
make build    # nodes/chunks/ingest_report/fallback_map
make rules    # rules/*.yaml có evidence nguyên văn
make golden && make eval
python -m scripts.ablate_header all
make serve    # http://127.0.0.1:8000/docs
```

`rules/*.yaml`, `data/processed/`, `data/index/`, `data/ingest_report.json` không commit vì chứa
text luật (rule 4) — tái tạo bằng `make rules` và `make build`.

## 7. Danh mục artifact + sha256

| Artifact | sha256 |
|---|---|
| `results/parse_stats.json` | `0f9f161960d467f42b2f5c0b0076969b5d584310218a0d9c5b61105c55bcc84a` |
| `data/ingest_report.json` | `afd899fa04dc838ebbcf5fa9362c9988ced2df6747f051d77f1a86a309378a84` |
| `eval/qa_eval.jsonl` | `f4d1d4a66558bcf6b11a16919af116c91a3f63b4e35dd7bcddbdbae7f57b1352` |
| `eval/calc_eval.jsonl` | `306a0920f799b0004b4251d7dc5f5a415670a65baa7cbfa17617c1706df6ade9` |
| `results/eval_report.json` | `f8555d42b97f1aa1488c09e81bd518a4fdfa232edb00bc26dd820359d8268414` |
| `results/eval_dev.json` | `c23db9bf4594d1fe217787a7c8981bcae924cb475a0e9211e47d82d3bf51368f` |
| `results/eval_test.json` | `6b73c65c853a0741d4dd1183381ccf4baa65622ab283efaa6e3c4fecb282331a` |
| `results/header_ablation.json` | `09fa6a1a35cf7c811bb723fda0830c6f495895c309f17971cec88b1dd19382d7` |
| `results/retrieval_ablation.json` | `071cc65497126e77bdd6c89da510b5d5194d8a709e14eff76bba8d38aac13758` |

Model đã tải (không commit): `BAAI/bge-m3`, `intfloat/multilingual-e5-large` trong `HF_HOME`.
Cache dense: `data/index/dense-{bge-m3,e5-large}-973e4ab6c318.npy` (1603×1024 float32, ~6.6 MB mỗi file).
