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
- Danh tính hai file (file nào là bản gốc, file nào là bản hợp nhất) mới suy ra từ metadata
  (kích thước, ngày tạo, phần mềm scan), **chưa** xác nhận bằng nội dung.
- Xác nhận nội dung là gate của T00b: bản gốc phải chứa `45/2019/QH14`, bản hợp nhất phải chứa `VBHN`.
  Nếu không khớp → dừng và báo người dùng (PLAN §6.1).