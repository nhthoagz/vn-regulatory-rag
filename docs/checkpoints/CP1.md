# CP1 — Ingest (T00b → T07b)

- Ngày chốt: 2026-11-28
- Artifact gốc: `data/ingest_report.json` (`generated_at 2026-11-27T19:48:12Z`, `as_of 2026-11-27`,
  `status ok`), sha256 `afd899fa04dc838ebbcf5fa9362c9988ced2df6747f051d77f1a86a309378a84`
- Bộ đo chi tiết: `results/parse_stats.json`

## 1. Tiêu chí gate (PLAN §5 / CP1)

| Tiêu chí | Kết quả | Đạt? |
|---|---|---|
| Bản gốc đủ 220 Điều, 17 Chương | 220 Điều, 17 Chương, 585 Khoản, 228 Điểm | ✅ |
| Bản hợp nhất: 216 Điều + đúng 4 Điều thiếu được đánh dấu | 216 Điều, `missing_articles=[76, 77, 78, 79]` | ✅ |
| Không có `node_id` trùng | `node_id_unique=true` cho cả hai văn bản | ✅ |
| Không có issue mức `error` | 0 error / cả hai | ✅ |
| `evidence` của rule ⊂ node text | `tests/test_rules.py` pass | ✅ |

## 2. Số đo (copy từ ingest report)

| Văn bản | Trang | Node | Chương | Điều | Khoản | Điểm | Chunk leaf/clause/article |
|---|---|---|---|---|---|---|---|
| `18-VBHN-VPQH-2026` (mặc định) | 86 | 1104 | 17 | 216 | 595 | 253 | 818 / 632 / 216 |
| `45-2019-QH14` (gốc) | 83 | 1071 | 17 | 220 | 585 | 228 | 785 / 625 / 220 |

sha256 (12 ký tự đầu, đầy đủ trong `data/ingest_report.json`): nodes `f8b4e1a83653`,
chunks leaf `973e4ab6c318`, clause `f75ccbaf5b6a`, article `4d359be54a37`.

## 3. Khuyết tật nguồn đã ghi nhận (không sửa được bằng code)

1. Bản hợp nhất **mất 2 trang in (33–34)**: số trang in nhảy 32 → 35 giữa pdf trang 32 và 33
   (`scan_page_anomalies.missing_printed_pages`), kéo theo thiếu Điều 76–79. Xử lý: trả lời từ bản gốc
   kèm câu cảnh báo bắt buộc (`data/index/fallback_map.json`).
2. Bản scan **đảo trang in 15/16** (`swapped_printed_pages`): loader sắp lại theo số trang in, nên
   Điều 35 không còn bị gộp vào Điều 36.

## 4. Kết luận

**PASS**, kèm 2 khuyết tật nguồn ở §3 đã được xử lý tường minh và có test.
Điều kiện còn treo: người dùng duyệt nội dung 4 file review OCR (`data/raw/review/*.md`) — chưa có xác nhận.
