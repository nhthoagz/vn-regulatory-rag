# vn-regulatory-rag

Hỏi đáp và tính toán trên văn bản quy phạm tiếng Việt phân cấp (Chương > Mục > Điều > Khoản > Điểm),
với trích dẫn **kiểm chứng được bằng code** và số liệu tính toán do tool `Decimal` sinh ra.

- Miền đầu tiên: Bộ luật Lao động 2019 (45/2019/QH14), đối chiếu với bản hợp nhất VBHN.
- Tài liệu: [SPEC.md](SPEC.md) (yêu cầu kỹ thuật) · [PLAN.md](PLAN.md) (kế hoạch và checkpoint).
- Trạng thái: **khung repo (T00)**. Chưa có index, chưa có golden set, chưa có số liệu đánh giá.

Mọi con số trong README này, khi được bổ sung, phải copy từ `results/*.json` kèm timestamp và sha256.
Số nào chưa sinh ra được từ artifact thì không được viết vào đây.

## Tiến độ

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0 | Khung repo, `.gitignore`, CI-lint | đang làm |
| 1 | OCR 2 file scan → `*-ocr.pdf` + sidecar | chưa |
| 2 | Config + test harness | chưa |
| 3 | Parse Điều/Khoản/Điểm, bảng, vòng đời | chưa |
| 4 | Truy xuất (BM25 + dense + fusion + OOS) | chưa |
| 5 | Sinh câu trả lời + guard trích dẫn/số liệu | chưa |
| 6 | Tool tính toán + rules có evidence | chưa |
| 7 | Golden set + eval | chưa |
| 8 | Ablation | chưa |
| 9 | API, UI, Docker, CI | chưa |
| 10 | Báo cáo final | chưa |

## Dữ liệu

- PDF luật và mọi dạng text suy ra từ PDF **không được publish** (`.gitignore` chặn `data/raw/*`,
  `data/processed/`, `data/index/`).
- Người dùng tự đặt file vào `data/raw/`; `data/raw/SOURCES.md` (được track) ghi tên file, sha256 và ngày copy.
- Không crawl vbpl.vn.

## Chạy thử

```bash
# 1) môi trường (WSL2, Python 3.11 qua uv)
make setup      # uv sync vào ~/.venvs/vn-rag

# 2) kiểm tra
make check      # ruff + pytest (bỏ qua test cần dữ liệu thật)
make t T=tests/test_smoke.py
```

## Giới hạn đã biết

- Hệ thống không bảo đảm "không ảo giác". Guard chỉ kiểm được: tập `node_id` được trích,
  định dạng trích dẫn, và mọi con số phải có trong nguồn đã truy xuất hoặc trong output tool.
  Trích đúng nguồn nhưng diễn giải sai vẫn có thể xảy ra; đó là lý do có `verify_quotes` và
  `numeric_mismatch` trong báo cáo.
- Golden set do LLM sinh và agent tự curate (`author: llm`, `verified_by: agent`), không phải
  người viết tay; mọi báo cáo phải ghi rõ điều này khi trích số liệu.
- Câu trả lời về mức lương tối thiểu, ngày phép luôn gắn nhãn "mức tối thiểu" và nêu giả định.