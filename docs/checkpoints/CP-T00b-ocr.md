# CP-T00b — OCR hai văn bản nguồn

Gate: **PASS** (chạy 2026-11-27, mọi số copy từ `results/ocr_report.json` và `results/ocr_report_best_orig.json`).

## 1. Cấu hình đã dùng

| Mục | Giá trị |
|---|---|
| ocrmypdf | `16.13.0` |
| tesseract | `5.5.0` (lang `vie`, `eng`, `osd`) |
| Ghostscript | 10.6.x — in cảnh báo mã hóa JPEG, đã ghi vào `stderr_tail` của report |
| Cờ | `-l vie --rotate-pages --deskew --clean --invalidate-digital-signatures --jobs 4` |
| Cờ bắt buộc phát sinh | `--invalidate-digital-signatures` vì **cả hai PDF có chữ ký số** |
| Ngưỡng | ≥ 50 ký tự / trang; ≥ 95% trang phải đạt |

## 2. Đầu ra và số đo

| File | Byte | Trang | Trang đạt | Tỷ lệ | sha256 |
|---|---|---|---|---|---|
| `data/raw/blld2019-18-vbhn-vpqh-2026-ocr.pdf` | 38 408 874 | 86 | 86 | 1.0 | `a355822c461cfcf2319e52733889bb4319819c7eb0cd5bb73df9eed8a528ba6c` |
| `data/raw/blld2019-45-2019-qh14-goc-ocr.pdf` | 5 451 554 | 83 | 83 | 1.0 | `83dd0566e8607d81937bb5d8d8abdf6ac589635b156433543e955ac927f6bb59` |

- Tổng thời gian một lần chạy cả hai file: **285 s** (`total_seconds` trong `results/ocr_report.json`).
- Sidecar text: `data/raw/*.txt` (254 374 và 257 384 byte).
- File rà soát: `data/raw/review/*.md` (mỗi trang có `=== Trang N ===`) — gitignored, chỉ ở máy.

## 3. Xác nhận danh tính văn bản

| doc_id | Marker | Tìm thấy ở trang | Kết luận |
|---|---|---|---|
| `18-VBHN-VPQH-2026` | `VBHN` | 86 (khối ký) | trang 1 ghi "Bộ luật Lao động số 45/2019/QH14 … được sửa đổi, bổ sung…", trang 86 ghi "Số: 18/VBHN-VPQH" → **đúng là bản hợp nhất** |
| `45-2019-QH14` | `45/2019/QH14` | 1 | **đúng là bản gốc** |

## 4. So sánh model (quyết định dựa trên số liệu)

Chạy thêm `tessdata_best` (vie) trên bản gốc 83 trang, cùng cờ, kết quả ở
`results/ocr_report_best_orig.json`: 83/83 trang, `all_pass=True`, 155.1 s.

Chỉ số cấu trúc (`scripts/ocr_metrics.py`, cùng một văn bản):

| Chỉ số | `vie` (chuẩn) | `vie` (best) |
|---|---|---|
| `chapters` | 12 | 11 |
| `articles_with_dot` | 211 | 208 |
| `articles_any` | 231 | 234 |
| `clause_markers_dot` | 611 | 605 |
| `clause_markers_comma` | 20 | 26 |
| `point_markers` | 253 | 262 |
| `chars` | 191 442 | 191 374 |

Ví dụ đối chứng (Điều 98):

| Nguồn | Câu dẫn | Điểm a) |
|---|---|---|
| model chuẩn | "…đang làm **như sau**:" đúng | đọc thành **"3)"** sai |
| model best | "…đang làm **như san**:" sai | **"a)"** đúng |

Lỗi chung của cả hai: số La Mã của Chương bị đọc sai — chuẩn cho `l, H, HI, VIH, XIHI`;
best cho `I, H, II, VH, VHI, XH, XHI, XVH`. Số La Mã thật là `I..XVII` (17 chương).

**Quyết định: giữ model chuẩn (`tesseract-ocr-vie`).**
Không chỉ số nào chứng minh best tốt hơn một cách hệ thống (3 chỉ số tốt hơn, 4 chỉ số xấu hơn,
chênh lệch trong sai số của một lần chạy). Đổi model vì "nghe chính xác hơn" là quyết định cảm tính,
trái với yêu cầu không làm đẹp số liệu.

**Hệ quả bắt buộc (đã đưa vào SPEC §6.1/§6.3):** lỗi số La Mã và lỗi `.` → `,` phải được xử lý ở
tầng parse, không phải bằng cách đổi model:
1. Dòng tiêu đề `Chương …` được OCR lại cục bộ bằng `--psm 7` với
   `-c tessedit_char_whitelist="IVXLCDM "` trên vùng ảnh của chính dòng đó (300 DPI).
2. Kiểm tra tính đơn điệu: 17 chương phải cho dãy `I..XVII` liên tục; nếu lệch thì báo lỗi ra
   `ingest_report.json`, không tự đoán.
3. Regex khoản chấp nhận cả `1.` và `1,`.

## 5. Hạn chế đã biết (không được che)

- Gate "≥ 50 ký tự/trang" chỉ chứng minh **trang có text**, **không** chứng minh **text đúng ký tự**.
  Đây là lý do phải có thêm danh sách "điều cần soi" từ đối chiếu chéo hai bản (SPEC §6.8).
- Lỗi ký tự quan sát được: `kiến → kiên`, `tổ → tô`, `sau → san`, `a) → 3)`, `.` → `,`.
- Trang 1 bản gốc gần như chỉ có nội dung khối chữ ký số ("Ký bởi: Cổng Thông tin điện tử Chính phủ"),
  phần tiêu đề bị OCR kém; tiêu đề lấy từ bản hợp nhất.
- `articles_any` (231/234) > 220 vì có mục lục cuối văn bản → parser phải cắt mục lục trước khi đếm.

## 6. Bước kế tiếp

- T03: `normalize`, `ids`, `schema` + test.
- T04/T05: loader pdfplumber, parser với bản sửa số La Mã và cắt mục lục.