# Ghi chú bảo vệ / phỏng vấn

## Bài toán

Trả lời câu hỏi pháp lý lao động **có trích dẫn kiểm chứng được** trên hai PDF luật scan (bản gốc
2019 và bản hợp nhất 2026), kèm tính toán định lượng (làm thêm giờ, nghỉ hằng năm).

## Kiến trúc (một chiều, đo được từng chặng)

`PDF scan → OCR có cổng kiểm → parse Chương/Mục/Điều/Khoản/Điểm (node_id) → chunk 3 tầng
→ BM25 (+dense tuỳ chọn, fusion RRF/linear) → guard 3 luật → trả lời trích nguyên văn + citation`

## 5 quyết định đáng nói

1. **OCR-first có cổng**: không parse ảnh; chỉ parse khi 83/83 và 86/86 trang có text layer, và
   xác nhận danh tính bằng nội dung (không tin metadata).
2. **`node_id` có cấu trúc** (`doc:D98.K1.a`): trích dẫn trỏ đúng đơn vị, không phải "trang 12".
3. **Guard bằng code, không bằng lời hứa**: citation ⊆ nguồn, mọi con số ⊆ nguồn ∪ câu hỏi ∪ tool,
   bắt buộc cảnh báo khi dùng bản gốc thay bản hợp nhất.
4. **Khuyết tật nguồn xử lý tường minh**: bản hợp nhất mất trang in 33–34 → thiếu Điều 76–79 →
   `fallback_map.json` + cảnh báo; đảo trang 15/16 → sắp lại theo số trang in.
5. **Số liệu phải tái tạo được**: mọi con số trong tài liệu copy từ `results/*.json` kèm sha256;
   `make build/rules/eval` sinh lại được.

## Kết quả (copy từ artifact, xem `docs/FINAL_REPORT.md`)

- Ingest: gốc 17 Chương/220 Điều; hợp nhất 17/216 + thiếu `[76,77,78,79]`; 0 lỗi; node_id duy nhất 100%.
- Trả lời: article 1.00, clause 1.00, fallback 1.00, OOS 0.95, calc 30/30, 1 vi phạm guard.
- Ablation header (BM25): `true` P@5 0.1389 vs `none` 0.0044 vs `placebo` 0.0056.

## Trung thực về giới hạn

- P@5 mức node thấp vì gold là **toàn bộ node của một Điều**; độ đúng trả lời đo bằng `gold_cited`.
- Ablation header phần lớn phản ánh việc câu hỏi chứa "Điều N" khớp header — không phải bằng chứng
  hiểu ngữ nghĩa.
- Dense/reranker: có code + số đo; **LLM viết câu trả lời chưa bật** vì `sudo` cần mật khẩu để cài
  Ollama (không cài phi tương tác được) → hệ thống chạy extractive, client LLM có sẵn và tắt mặc định.

## Nếu có thêm thời gian

Reranker cross-encoder trên top-20; LLM viết câu trả lời có kiểm chứng (guard đã sẵn); mở rộng
cross-reference; calibrate OOS trên tập lớn hơn; human review bộ đề trước khi đóng băng test set.
