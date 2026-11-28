# PLAN — vn-regulatory-rag

## 0. Trạng thái hiện tại

> **Ghi chú lịch sử (trước T00).** Các gạch đầu dòng dưới đây là ảnh chụp lúc bắt đầu dự án.
> Trạng thái **hiện tại** xem §0.1 ngay sau đây; số liệu chi tiết ở `docs/FINAL_REPORT.md`.

- Thư mục `E:\Projects\vn-regulatory-rag` (WSL: `/mnt/e/Projects/vn-regulatory-rag`) **đã được người dùng tạo**, đang trống.
  Không cần `mkdir` cho thư mục gốc; chỉ tạo các thư mục con trong T00.
- Tên repo GitHub: `nhthoagz/vn-regulatory-rag`, **public**.
- Hai file PDF luật nằm ở `E:\Projects\` (tên đã được người dùng đặt đúng theo SPEC §2).
  Chỉ **COPY** sang `data/raw/`, không move, không đổi tên.
- Ảnh trong PDF là ảnh scan, không có text layer → phải OCR trước khi parse (T00b).

### 0.1 Trạng thái thực tế (cập nhật 2026-11-28)

- Repo public đã có commit; tag đã gắn: `cp1-ingest`, `cp2-pipeline`.
- OCR xong: bản gốc 83/83 trang, bản hợp nhất 86/86 trang; danh tính hai file đã xác nhận bằng nội dung.
- Ingest xong: bản gốc 17 Chương / 220 Điều; bản hợp nhất 17 Chương / 216 Điều thiếu `[76, 77, 78, 79]`
  (nguồn mất trang in 33–34), 0 lỗi parse, `node_id` duy nhất 100%. Chunk 3 tầng: 1603 / 1257 / 436.
- Có `rules/*.yaml` sinh từ text (13 rule, mỗi rule có câu trích nguyên văn), BM25 + guard + API FastAPI,
  bộ đề 200 câu + 30 case, ablation header.
- Số liệu và sha256 của từng artifact: `docs/FINAL_REPORT.md`. Không chép số vào đây để tránh lệch.
- Còn lại (đang làm): dense embedding + fusion + ablation đầy đủ, LLM client/agent, OOS bảng FPR,
  tài liệu bàn giao. `rules/*.yaml`, `data/processed/`, `data/index/`, `data/ingest_report.json` không commit
  vì chứa text luật — tái tạo bằng `make rules` và `make build`.

## 1. Chuẩn bị một lần (việc của người dùng, trước T00b)

```bash
sudo apt update && sudo apt install -y ocrmypdf tesseract-ocr tesseract-ocr-vie \
  tesseract-ocr-osd poppler-utils ghostscript unpaper
```

- `gh` CLI đã đăng nhập (`nhthoagz`, scope `repo` + `workflow`). `git config` đã có name/email.
- Kiểm tra nhanh: `command -v ocrmypdf tesseract pdftotext` phải in ra 3 đường dẫn.
- Không có gói này thì T00 vẫn chạy được, chỉ T00b bị chặn.

## 2. Nguyên tắc làm việc

1. Một task mỗi lần, theo đúng thứ tự trong §4. Không nhảy cóc.
2. Test-first. Task xong khi `make t T=<path>` exit 0 **và** `ruff check .` exit 0.
3. Dừng ở mọi dòng đánh dấu 👤 trong §4 (cần người dùng) hoặc điểm ghi "STOP".
4. Commit theo conventional commit sau mỗi task đã pass: `feat(ingest): parse Điều/Khoản/Điểm`.
   Một commit = một task. Tag `cpN-<slug>` ở mỗi checkpoint đã duyệt.
5. Không bịa số liệu. Mọi con số trong tài liệu copy từ `results/*.json`, kèm timestamp + sha256.
6. Tự rà soát trước khi báo xong task: chạy lại lệnh kiểm tra 2 lần (kỳ vọng kết quả giống nhau),
   đọc diff, soát `git status` (không có file dữ liệu/secret), xem lại output thật.
7. Dừng và hỏi ngay khi gặp điều kiện ở §6. Không "đoán cho xong".
8. Không ghi đè `SPEC.md` và `PLAN.md`. Nếu cần đổi spec, sửa file và ghi lý do ở commit message.

## 3. Lệnh hay dùng

Tất cả chạy trong WSL: `cd /mnt/e/Projects/vn-regulatory-rag`.

`uv` nằm ở `~/.local/bin`, chỉ có trong PATH của **login shell**. Shell không-login (vd `wsl.exe -e bash script.sh`)
phải `source scripts/env.sh` ở đầu script; file này export `PATH`, `UV_PROJECT_ENVIRONMENT`,
`HF_HOME`, `PYTHONUTF8`. Gọi `uv` trực tiếp mà không có 3 biến này sẽ tạo `.venv` ngay trong repo
(sai, vì venv phải nằm trên ext4 tại `~/.venvs/vn-rag`).

| Mục | Lệnh |
|---|---|
| Cài / cập nhật env | `make setup` (uv sync vào `~/.venvs/vn-rag`) |
| Lint + test nhanh | `make check` |
| Test một file | `make t T=tests/test_parser.py` |
| OCR | `make ocr` (job > 60 s → `nohup make ocr > logs/ocr.log 2>&1 &`) |
| Build index | `make ingest ingest-report index` (job dài → `nohup`) |
| Ablation | `make ablation` (job dài → `nohup`) |
| Chạy API | `make api` |
| Rà soát rò rỉ trước push | `make leak` |

`make leak` đọc `git ls-files` và fail nếu có `.env`, `*.pdf`, `*.pt`, `*.onnx`, `*.npy`,
`data/raw/*` (trừ `SOURCES.md` và `.gitkeep`), `data/processed/`, `data/index/`.
Chỉnh logic trong `scripts/check_leak.py`, test ở `tests/test_leak_check.py`.

Khi lệnh chạy qua PowerShell (nếu không phải phiên WSL), bọc dạng `wsl.exe -e bash -lc '<lệnh>'` với **nháy đơn**.
Không dùng `$VAR` không escape trong chuỗi nháy kép. Tránh pipe `|` và ngoặc kép lồng nhau trong lệnh
truyền qua `wsl.exe`; việc gì phức tạp thì viết thành script Python trong `scripts/` rồi gọi qua `uv run`.

Cảnh báo môi trường: `E:\` là ổ Windows. Job ghi nhiều (OCR, embedding) sẽ chậm hơn trên ext4;
chấp nhận vì dữ liệu nhỏ, nhưng **không** đặt `HF_HOME` hay model cache trong `/mnt/e`.

## 4. Danh sách task

### Phase 0 — Khung repo

| Task | Nội dung | Verify |
|---|---|---|
| **T00** | `git init`; `.gitignore` (chặn `data/raw/*` trừ `SOURCES.md`, `data/processed/`, `data/index/`, `.env`, `*.pt`, `*.onnx`, `*.npy`); `.gitattributes` (`*.pdf`, `*.npy`, `*.onnx` binary); `.env.example`; `pyproject.toml` (Python 3.11, deps + `[dependency-groups] dev = pytest, ruff`); Makefile (`setup/lint/test/t/check`); README; `.clinerules/rules.md`; `tests/test_smoke.py`; tạo cây thư mục | `make check` exit 0; rà soát rò rỉ; commit đầu; `gh repo create ... --public --push` |
| 👤 **CP0** | Người dùng xem repo trên GitHub | Repo public, không có PDF/text/.env |

### Phase 1 — OCR

| Task | Nội dung | Verify |
|---|---|---|
| **T00a** | COPY 2 PDF vào `data/raw/`, viết `data/raw/SOURCES.md` (file, sha256, cách copy, ngày). Không move, không đổi tên | sha256 hai bên khớp; `SOURCES.md` được track, PDF bị ignore |
| **T00b** | `scripts/ocr.py` + `make ocr`: chạy ocrmypdf cho từng file (SKIP nếu đã có `*-ocr.pdf`), tạo `.txt`, `review/<doc>.md`, `results/ocr_report.json`. Xác nhận danh tính file: bản gốc chứa `45/2019/QH14`, bản hợp nhất chứa `VBHN` | job dài bằng `nohup`; ≥ 95 % trang đạt; danh tính khớp |

### Phase 2 — Config và test

| Task | Nội dung | Verify |
|---|---|---|
| **T01** | `config/*.yaml` + loader Pydantic (`docs.yaml`, `retrieval.yaml`, `llm.yaml`, `rules`, `synonyms`, `intents`, `thresholds`, `ocr_fixes`). **Điền được thì điền, không được thì để `null` + ghi rõ nguồn cần lấy** | test load; `make check` |
| **T02** | `tests/conftest.py`: `pdf_path`, `nodes` (từ `nodes.jsonl`, `pytest.skip` nếu chưa có), `fake_llm`; `tests/fixtures/sample_lines.json` | `pytest` pass; không test nào lặng lẽ pass khi thiếu dữ liệu |

### Phase 3 — Parse/ingest

| Task | Nội dung | Verify |
|---|---|---|
| **T03** | `src/common/normalize.py` (NFC, dấu thanh, `strip_diacritics`), `schema.py` (`Node`, `Segment`, `DocMeta`), `ids.py` (`make_node_id`, `parse_node_id`, round-trip) | unit test: `hoà` và `hòa` chuẩn hóa về cùng một dạng; `Điều 2a` → `D2a`; `đ` → `d` |
| **T04** | `src/ingest/loaders.py`: pdfplumber (dòng + tọa độ), bỏ header/footer/số trang, `page_span`, tách khối chú thích VBHN | test trên fixture; số trang > 0; không mất dòng bất thường |
| **T05** | `src/ingest/parser.py`: Chương/Mục/Điều/Khoản/Điểm + `lead_in` + monotonic check | unit test + integration test trên `*-ocr.pdf` thật |
| **T06** | `src/ingest/refs.py` (resolve), `tables.py` (bảng → `table_md`), `lifecycle.py` (`filter_active`) | test `has_exception`: "khấu trừ" → `False`; "trừ trường hợp" → `True`; test bảng |
| **T07** | `src/ingest/normalize_text.py` + `build.py` + `make ingest ingest-report`: `nodes.jsonl` (sort, sha256), `ingest_report.json` (số chương/điều/khoản/điểm/bảng, thiếu, lạ, đối chiếu chéo 2 bản) | 2 lần chạy cùng sha256; report có `expected_counts` đã xác nhận |
| 👤 **CP1** | Người dùng duyệt cấu trúc bằng số liệu report + 5 điều khoản mẫu | Số liệu khớp văn bản; không có Điều giả/mất |
| **T08** | `make ingest-report` nâng cấp: xuất `docs/ingest_summary.md` (số liệu từ JSON) và danh sách "điều cần soi" từ diff 2 bản | `make check`; file .md chỉ chứa số lấy từ JSON |

### Phase 4 — Retrieval

| Task | Nội dung | Verify |
|---|---|---|
| **T09** | `src/retrieve/tokenize.py` (`synonyms.yaml`), `bm25.py` (2 trường), `chunk.py` (3 tầng + `header_mode`), `src/retrieve/dense.py` (e5-large; bge-m3; cache `.npy` + meta), `fusion.py` (linear α, min-max, z-score, RRF), `retriever.py` (mode, `as_of`, điểm thô), `expand.py`, `oos.py` (ngưỡng thô), `reranker.py` (cờ bật), `make index` | unit test cho mỗi module; integration test không tải model (dùng vector giả lập) |
| **T10** | `make index-real`: build vector thật cho bge-m3 (fallback e5 nếu OOM). Log thời gian, RAM, VRAM | job dài bằng `nohup`; `make t T=tests/integration` pass |

### Phase 5 — Sinh câu trả lời

| Task | Nội dung | Verify |
|---|---|---|
| **T11** | `src/common/llm.py` (OpenAI-compatible, timeout, backoff, A→B→extractive), `src/common/jsonparse.py` (parse JSON bền) | unit test với `FakeLLM` + sai định dạng |
| **T12** | `src/common/core.py`: `Answer`, `retrieve → prompt → generate → guard → retry 1 → extractive` | test: guard fail thì gọi fallback; không quá 2 lượt LLM |
| **T13** | `src/guard/citations.py`, `numeric.py`, `sentences.py`, `report.py`, `extractive.py` | test `"1.000.000"`, `"v.v."`, `"01/01/2021"`; test trích dẫn ngoài tập |
| **T14** | `src/guard/verify.py` + `scripts/verify_quotes.py`: kiểm mọi `[[node_id]]` tồn tại và câu trích đúng nguyên văn | báo cáo % khớp; exit != 0 nếu có trích sai |

### Phase 6 — Tool tính toán + rules

| Task | Nội dung | Verify |
|---|---|---|
| **T15** | `rules/*.yaml`: overtime rate, annual leave, holidays, night premium — **chỉ các giá trị trích được nguyên văn từ OCR**; `src/tools/rules.py` + test `evidence ⊂ node.text` và `str(value) ⊂ evidence` | test exit 0; rule thiếu evidence bị từ chối |
| **T16** | `src/tools/money.py` (parse `"5 triệu"`, `Decimal`, quantize), `overtime.py`, `leave.py`, `assumptions.py` | unit test: 5.000.000đ + 10 giờ ban ngày; 6 tháng → `Decimal("6")` chưa làm tròn |
| **T17** | `src/agent/router.py` (regex + kNN `intents.yaml`), `slots.py` (regex → Pydantic, hỏi lại), `calc.py` (tool → diễn đạt → guard), `qa.py`, `oos.py` | test thiếu slot → câu hỏi lại; test giả định sai → sửa lại giả định |
| **T18** | Nối `core.answer`: QA + calc + OOS + guard + fallback | test end-to-end với `FakeLLM` |
| 👤 **CP2** | Người dùng kiểm 2 chức năng tính + 3 câu hỏi QA trên 50 Điều đầu | Số liệu đúng; trích dẫn đúng |

### Phase 7 — Golden set + eval

| Task | Nội dung | Verify |
|---|---|---|
| **T19** | `scripts/build_golden.py`: `qa_eval.jsonl` 200 câu + `calc_eval.jsonl` 30 case (phân bố theo SPEC §11); `author: llm`, `verified_by: agent`; dev/test 50/50 theo điều khoản gold; thống kê phân bố | `make eval-validate`: đếm đúng 200/30, không trùng `qid`, mọi `gold_node_ids` tồn tại trong `nodes.jsonl` |
| **T20** | `scripts/build_eval_index.py`: bỏ 20 % chunk theo seed 42; lưu danh sách đã bỏ | hai lần chạy cùng danh sách; gold luôn nằm trong phần còn lại |
| 👤 **CP3** | Golden set đóng băng: người dùng đọc 10 câu mẫu tùy ý | Không có câu vô nghĩa / trùng |
| **T21** | `src/evaluation/metrics.py` (P@5, R@10, nDCG@10, MRR@10, bootstrap CI95, paired diff trên cùng qid) | test với ví dụ tính tay đúng |
| **T22** | `scripts/run_eval.py` + `make eval`: BM25 2 trường, dense bge-m3, linear α = 0.7, RRF; **cả 3 tầng chunk**; ghi `results/retrieval_*.json` | job dài bằng `nohup`; JSON có đủ metric + CI |
| **T23** | OOS: sweep ngưỡng trên dev (cosine top-1, BM25 thô) → chọn ngưỡng → `results/oos_thresholds.json` + bảng ngưỡng ↔ FPR + cross-tab 2×2 | FPR của unanswerable đo được; chốt ngưỡng trước khi đụng test |
| 👤 **CP4** | Người dùng duyệt ngưỡng OOS + bảng FPR | FPR chấp nhận được |

### Phase 8 — Ablation

| Task | Nội dung | Verify |
|---|---|---|
| **T24** | `scripts/run_ablation.py`: α 0.0→1.0, header_mode none/true/placebo, bỏ `strip_diacritics`, min-max vs z-score, RRF | `results/ablation_*.json` đầy đủ, có CI |
| **T25** | Reranker: chỉ bật nếu CI95 Δ > 0 **và** p95 ≤ 1 s; nếu không đạt, ghi lý do vào report và giữ tắt | quyết định có số liệu kèm |
| **T26** | Retrieval-only vs QA vs QA + guard; `max_baseline_len` 512 | `results/answer_*.json` |
| **T27** | `scripts/run_eval_answers.py` (chạy test set một lần, chốt): `cite_precision`, `gold_cited`, `numeric_mismatch` (code) + `judge_pass` + `faithfulness_judge`/`answer_correctness_judge` (LLM khác họ) | `results/answers_test.json` + log `judge_model` |
| 👤 **CP5** | Người dùng duyệt bảng kết quả ablation + chất lượng câu trả lời | Số liệu thật, không làm đẹp |

### Phase 9 — API/UI/deploy

| Task | Nội dung | Verify |
|---|---|---|
| **T28** | `src/api/main.py` (FastAPI: `/health`, `/ask`, `/calc/overtime`, `/calc/leave`), `scripts/run_api.sh` | `curl` 4 endpoint OK |
| **T29** | `src/ui/app.py` (Gradio: trả lời + trích dẫn + trạng thái guard/OOS) | chạy local, 3 câu mẫu |
| **T30** | `Dockerfile` (CPU, model đóng băng), `.github/workflows/ci.yml` (ruff + pytest), `deploy.md` | `make check` pass; CI xanh; Dockerfile build được (nếu không build được thì ghi lý do) |

### Phase 10 — Báo cáo

| Task | Nội dung | Verify |
|---|---|---|
| **T31** | `docs/FINAL_REPORT.md` (số liệu copy từ JSON, bảng ablation, giới hạn, cách tái lập), `docs/INTERVIEW_NOTES.md` (kiến trúc + 15 câu hỏi phỏng vấn), `README.md` cập nhật, `results/summary.json` | Mọi con số trong .md tìm thấy trong JSON; `make check` pass |
| **T32** | Tag `v0.1.0`, push, rà soát rò rỉ lần cuối | Repo public không có PDF/text luật/`.env` |

## 5. Checkpoint và gate tự động

Mỗi checkpoint là một **gate có tiêu chí máy kiểm được**; pass thì ghi `docs/checkpoints/CPn.md`
(gồm số liệu, lệnh verify, sha256 artifact) và đi tiếp.

| CP | Sau task | Tiêu chí pass (máy kiểm) | Ghi chú |
|---|---|---|---|
| CP0 | T00 | `make check` exit 0; không có file dữ liệu trong `git ls-files`; repo public tồn tại | 👤 người dùng xem repo |
| CP1 | T07 (sau T08) | `nodes.jsonl` tất định (2 lần cùng sha256); số Điều/Khoản khớp `expected_counts` đã xác nhận từ OCR; không có Điều trùng/thiếu | 👤 duyệt 5 điều khoản mẫu |
| CP2 | T18 | test end-to-end với `FakeLLM` pass; 2 tool tính cho kết quả đúng với 3 case tính tay; guard chặn được trích dẫn ngoài tập | 👤 kiểm 3 câu QA |
| CP3 | T19–T20 | 200/30 câu đúng phân bố; gold thuộc phần không bị bỏ; dev/test rời nhau theo điều khoản | 👤 đọc 10 câu mẫu |
| CP4 | T23 | ngưỡng OOS chốt trước khi chạy test; FPR của unanswerable đo được và ghi bảng | 👤 duyệt ngưỡng |
| CP5 | T24–T27 | `results/ablation_*.json` + `results/answers_test.json` có đủ metric + CI; mọi nhận định trong report có số liệu | 👤 duyệt kết quả |
| CP6 | T28–T30 | 4 endpoint `curl` OK; `make check` pass; CI xanh | — |
| CP7 | T31–T32 | mọi số trong .md truy được về JSON; tag `v0.1.0`; rà soát rò rỉ OK | 👤 duyệt bản final |

## 6. Điều kiện dừng bắt buộc (không tự quyết)

Dừng và báo người dùng ngay khi:

1. Danh tính 2 file PDF không khớp SPEC §2 (bản gốc không chứa `45/2019/QH14`, hoặc bản hợp nhất không chứa `VBHN`).
2. OCR < 95 % trang đạt sau lần chạy `--oversample 300`.
3. Số Chương/Điều/Khoản parse được lệch `expected_counts` **sau 2 lần sửa**.
4. Một giá trị trong `rules/*.yaml` không tìm được câu trích nguyên văn trong `nodes.jsonl`.
5. Cùng một lỗi lặp 3 lần (circuit breaker).
6. Phát hiện file dữ liệu/secret sắp bị đẩy lên repo.
7. Cần `sudo` (cài gói, sửa cấu hình hệ thống) hoặc cần tài khoản/token bên ngoài.
8. Số liệu ablation/test trái kỳ vọng ghi trong SPEC §11 sau khi đã kiểm lại code và dữ liệu.

## 7. Deliverables cuối

- Index tất định: `data/index/{nodes.jsonl,bm25/*,dense/*}` + `data/ingest_report.json`.
- Golden set + bảng ablation + số liệu chất lượng câu trả lời trong `results/*.json`.
- API FastAPI + UI Gradio + `Dockerfile` + CI.
- `docs/FINAL_REPORT.md`, `docs/INTERVIEW_NOTES.md`, `docs/checkpoints/CP*.md`, `README.md` cập nhật.
- Tag `v0.1.0` trên repo public, không chứa dữ liệu luật hay secret.

### 7.1 Những gì KHÔNG được hứa trong báo cáo

- Không hứa "zero hallucination". Chỉ báo cáo: tỷ lệ trích dẫn kiểm chứng được, `cite_precision`,
  `numeric_mismatch`, tỷ lệ guard chặn, tỷ lệ fallback về extractive.
- Không so sánh với hệ thống RAG thương mại khi chưa chạy baseline trên cùng protocol.
- Không dùng golden set do agent sinh như thể "golden set chuẩn người viết": luôn ghi rõ `author: llm`.