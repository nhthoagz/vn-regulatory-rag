# CP0 — Khung repo

Gate: **PASS** (kiểm ngày 2026-11-27, mọi số dưới đây copy từ output lệnh, không chỉnh tay).

## 1. Môi trường đo được

| Mục | Giá trị | Lệnh |
|---|---|---|
| uv | `0.13.10 (x86_64-unknown-linux-gnu)` | `uv --version` |
| Python | `3.11.18` | `uv run python --version` |
| venv | `/home/nhthoagz/.venvs/vn-rag` | `ls -d "$UV_PROJECT_ENVIRONMENT"` |
| Repo | `github.com/nhthoagz/vn-regulatory-rag` (PUBLIC) | `gh repo view ... --json visibility` |

Ghi chú: `uv run` gọi ngoài `make` từng tạo `.venv` trong repo vì thiếu `UV_PROJECT_ENVIRONMENT`.
Đã xóa `.venv`; từ nay mọi script phải `source scripts/env.sh`.

## 2. Cổng chất lượng

| Cổng | Kết quả | Ghi chú |
|---|---|---|
| `make lint` (ruff) | pass, 0 lỗi | phải sửa 1 lỗi E501 ở `tests/test_leak_check.py` trước khi pass |
| `make leak` | `tracked files: 33`, `clean` | đã từng lọt `.msg` + `.tmp_finalize.sh`; đã untrack và thêm `.tmp_*.sh`, `.msg`, `.msg2` vào `.gitignore` |
| `pytest` | `9 passed` | 4 test smoke + 5 test leak-check |

## 3. Artifact và sha256 (tại commit chứa file này)

```
39040f3c13c20fea85b2a325e22b46d260061c4686690e530f50eed6fb4b8f3f  SPEC.md
21771a9f5bab661fd11406ac9bfa1e1e45ffd24e6547d20044fefc0e42b4677e  PLAN.md
5fd4f71dbc85b3c84585dce1a44d61e831cf8abf13aec26f1b298f90fddd40e8  Makefile
9b93f548daddc70df2bde4c5132f7da31e3f6d0aba572336b2633903fd9cd076  pyproject.toml
c66b02b5539c6de599250be4c835b1a88bf5eedf7a4b8d888a6b4d16ad7674aa  uv.lock
84dc19d57e18ce13f3eb5ffeca5f463235c61e07e15dcc6035f68d0cdae1e477  scripts/env.sh
```

## 4. Lịch sử commit tới CP0

| Commit | Nội dung |
|---|---|
| `67296a3` | `chore(scaffold)`: khung repo, SPEC, PLAN, lint+test gate |
| `fbf4802` | `chore(docs)`: ghi chú yêu cầu PATH cho shell không-login |
| `62a7b6a` | `chore(hygiene)`: bỏ track file tạm, thêm pattern vào `.gitignore` |
| commit này | thêm `scripts/env.sh` và `docs/checkpoints/CP0.md` |

## 5. Việc còn chặn

| Chặn | Trạng thái | Cần |
|---|---|---|
| OCR (T00b) | `ocrmypdf`, `tesseract`, `pdftotext`, `gs`, `unpaper` đều `MISSING` | người dùng chạy `sudo apt install ...` (PLAN §1) |
| T00a (copy PDF) | chưa làm | có thể làm ngay, không cần apt |

## 6. Bước kế tiếp

1. T00a: copy 2 PDF vào `data/raw/` (không move, không đổi tên), ghi `data/raw/SOURCES.md` với sha256.
2. Chờ apt xong để chạy T00b (OCR) bằng `nohup`, rồi đối chiếu danh tính file theo SPEC §2.