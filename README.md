# vn-regulatory-rag

Hỏi đáp và tính toán trên văn bản quy phạm tiếng Việt phân cấp (Chương > Mục > Điều > Khoản > Điểm),
với trích dẫn **kiểm chứng được bằng code** và số liệu tính toán do tool `Decimal` sinh ra.

- Miền đầu tiên: Bộ luật Lao động 2019 (45/2019/QH14), đối chiếu với bản hợp nhất VBHN.
- Tài liệu: [SPEC.md](SPEC.md) (yêu cầu kỹ thuật) · [PLAN.md](PLAN.md) (kế hoạch, §0.1 trạng thái) ·
  **[docs/FINAL_REPORT.md](docs/FINAL_REPORT.md)** (số liệu + sha256 artifact) ·
  [docs/deploy.md](docs/deploy.md).
- Trạng thái: đã qua CP0 → CP3. Có ingest, BM25 + dense/fusion, guard, API, eval, ablation.
  Chưa có reranker; LLM client có nhưng tắt (không cài được Ollama do `sudo` cần mật khẩu);
  Gradio UI mới là scaffold; Docker/CI mới ở mức file.

Mọi con số trong README này copy từ `results/*.json` kèm sha256 (xem `docs/FINAL_REPORT.md` §7).
Số nào chưa sinh ra được từ artifact thì không được viết vào đây.

## Tiến độ

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 0 | Khung repo, `.gitignore`, CI | xong |
| 1 | OCR 2 file scan (83/83 và 86/86 trang) | xong |
| 2 | Config + test harness (106 test nhanh, 11 realdata) | xong |
| 3 | Parse Điều/Khoản/Điểm: gốc 220 Điều, hợp nhất 216 (thiếu 76–79) | xong |
| 4 | Truy xuất BM25 + dense (bge-m3, e5-large) + fusion linear/rrf + OOS | xong |
| 5 | Trả lời trích nguyên văn + guard 3 luật | xong |
| 6 | Tool tính toán + 13 rule có evidence nguyên văn | xong |
| 7 | Bộ đề 200 câu + 30 case, eval | xong (chưa human review) |
| 8 | Ablation header + ablation retrieval 7 cấu hình | xong (chưa reranker) |
| 9 | API FastAPI (chạy), Docker + CI (file, chưa chạy), Gradio (scaffold) | một phần |
| 10 | Báo cáo final | xong (`docs/FINAL_REPORT.md`) |

### Kết quả chính (copy từ artifact)

- Trả lời: article 1.00 (120 câu), clause 1.00 (40), fallback 1.00 (20), OOS 0.95 (20), calc 30/30,
  1 vi phạm guard — `results/eval_report.json`.
- Retrieval: BM25 P@5 0.1389 / MRR 0.2615; **e5-large + linear P@5 0.1522 / MRR 0.3273** —
  `results/retrieval_ablation.json`.
- Ablation header: `true` P@5 0.1389 vs `none` 0.0044 vs `placebo` 0.0056 —
  `results/header_ablation.json`.

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