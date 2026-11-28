# Nguồn dữ liệu — `data/raw/`

PDF luật **không được commit**. `.gitignore` chặn `data/raw/*` và chỉ cho phép `SOURCES.md`, `.gitkeep`.
File này ghi metadata để tái lập môi trường; nó **không** chứa nội dung văn bản luật.

## 1. Manifest (giá trị đo bằng `sha256sum`, không chỉnh tay)

| File | sha256 |
|---|---|
| `blld2019-45-2019-qh14-goc.pdf` | `a0c0fcc3b9e040bcdcab70191f0ab95952183be94a6f5bc6424e8d3e85697139` |
| `blld2019-18-vbhn-vpqh-2026.pdf` | `5a01a5b4b778b78c7bc9372e3a7270735bd98c28160604bff95db06bb3345a6f` |

| File | Byte | doc_id dự kiến | Vai trò |
|---|---|---|---|
| `blld2019-45-2019-qh14-goc.pdf` | 5 232 503 | `45-2019-QH14` | bản gốc: đối chiếu, test vòng đời |
| `blld2019-18-vbhn-vpqh-2026.pdf` | 38 999 953 | `18-VBHN-VPQH-2026` | bản hợp nhất: văn bản mặc định |

## 2. Cách đưa dữ liệu vào

```bash
cd /mnt/e/Projects/vn-regulatory-rag
cp -n /mnt/e/Projects/blld2019-45-2019-qh14-goc.pdf data/raw/
cp -n /mnt/e/Projects/blld2019-18-vbhn-vpqh-2026.pdf data/raw/
sha256sum data/raw/*.pdf   # phải khớp bảng trên
```

- Người dùng đặt tên file; T00a chỉ **copy**, không move, không đổi tên.
- Thời điểm copy: `2026-11-27T08:16:13Z`.
- Kiểm tự động: `make t T=tests/test_sources_manifest.py` (marker `realdata`).

## 3. Trạng thái xác nhận

- sha256 nguồn và bản copy **khớp** cho cả hai file (đã đo).
- Danh tính hai file **đã xác nhận bằng nội dung** (T00b), ghi trong `results/ocr_report.json`:
  - bản gốc phát hiện marker `45/2019/QH14` ở trang pdf 1 (`identity_pages: [1]`);
  - bản hợp nhất phát hiện marker `VBHN` ở trang pdf 86, tức khối chữ ký `Số: 18/VBHN-VPQH`
    (`identity_pages: [86]`). Trang 1 của bản hợp nhất **cũng** chứa `45/2019/QH14` (tên luật gốc),
    nên `45/2019/QH14` không dùng được để phân biệt hai file.
- OCR đạt: bản gốc 83/83 trang, bản hợp nhất 86/86 trang (xem `results/ocr_report.json`).
- Sau OCR còn phát hiện khuyết tật nguồn: bản hợp nhất **mất 2 trang in (33–34)** nên thiếu
  Điều 76–79, và **đảo trang in 15/16**. Chi tiết + cách xử lý: `docs/FINAL_REPORT.md` §1.