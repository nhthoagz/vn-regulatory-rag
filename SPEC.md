# SPEC — vn-regulatory-rag

## 1. Mục tiêu và phạm vi

- Hỏi đáp và tính toán trên văn bản quy phạm tiếng Việt phân cấp (Chương > Mục > Điều > Khoản > Điểm).
  Miền đầu tiên: Bộ luật Lao động 2019 (45/2019/QH14).
- Cam kết đo được: trích dẫn được code kiểm chứng (id thuộc tập đã truy xuất, số liệu có trong nguồn).
  Không hứa "không ảo giác". Guard không bắt lỗi "trích đúng nhưng diễn giải sai".
- Đổi miền = thay `data/raw/`, `config/`, `rules/`, không sửa code.
- Ngoài phạm vi: tư vấn pháp lý, crawl web (không crawl vbpl.vn).
- Chi phí 0 đồng: model mở, LLM local (Ollama) hoặc API free-tier.
- Repo public: `github.com/nhthoagz/vn-regulatory-rag`. Không đẩy PDF, text luật hay `.env` lên repo.
- Dự án độc lập: không kế thừa code, config hay quy tắc của bất kỳ repo khác.

## 2. Dữ liệu nguồn (kiểm tra ngày 27/11/2026, tên file do người dùng đặt)

| File (E:\Projects → data/raw/) | Size | Trang | Ảnh | Producer, ngày tạo | Text layer | Vai trò | doc_id |
|---|---|---|---|---|---|---|---|
| blld2019-45-2019-qh14-goc.pdf | 4.99 MB | 83 | CCITT 1-bit, ~260 DPI | Kodak Alaris, 2019-12-12 | 0/83 | Bản gốc: đối chiếu, test vòng đời | 45-2019-QH14 |
| blld2019-18-vbhn-vpqh-2026.pdf | 37.19 MB | 86 | JPEG 8-bit, ~200 DPI | HP Scan, 2026-02-12 | 0/86 | Bản hợp nhất: văn bản mặc định | 18-VBHN-VPQH-2026 |

- Danh tính hai file được suy ra từ metadata (size, ngày tạo, máy scan), chưa phải nội dung.
  Sau OCR, T00b xác nhận bằng text trang 1: bản gốc phải chứa `45/2019/QH14`, bản hợp nhất phải chứa `VBHN`.
  Không khớp thì DỪNG và báo người dùng.
- Cả hai file là ảnh scan, không có text layer, nên OCR là bước bắt buộc (T00b).
- Ngày hiệu lực, `expected_counts` của bản hợp nhất, và nguồn tải: không được đoán.
  Giá trị lấy từ text OCR và chỉ được ghi vào config sau khi có câu trích dẫn (xem §12).

## 3. Môi trường

- WSL2 Ubuntu 26.04.1, 16 nhân, ~7 GB RAM, RTX 3050 Ti 4 GB VRAM. Đích deploy: 2 vCPU / 16 GB.
- Python 3.11 qua `uv` (0.13.10). `UV_PROJECT_ENVIRONMENT=~/.venvs/vn-rag`, `HF_HOME=~/.cache/huggingface`.
- Repo: `/mnt/e/Projects/vn-regulatory-rag`. Dữ liệu nhỏ (2 PDF, ~2k vector) nên đặt trên /mnt/e chấp nhận được.
- Gói hệ thống cần có: `ocrmypdf`, `tesseract-ocr`, `tesseract-ocr-vie`, `tesseract-ocr-osd`,
  `poppler-utils`, `ghostscript`, `unpaper`.
- VRAM: không nạp đồng thời embedder + reranker + LLM. Embed query trên CPU.
- Job chạy > 60 s: `nohup ... > logs/<task>.log 2>&1 &`; theo dõi bằng `tail`, `ps`, `nvidia-smi`, `free -g`.
- Secrets chỉ trong `.env` (python-dotenv). `config/llm.yaml` chỉ ghi **tên biến ENV**, không ghi giá trị key.

## 4. Kiến trúc

Ingest (offline):

```
PDF scan → ocrmypdf (vie) → *-ocr.pdf + .txt + review/*.md
         → loaders (pdfplumber: dòng + tọa độ; bỏ header/footer/số trang; tách chú thích VBHN)
         → parser → refs → tables → lifecycle → nodes.jsonl + ingest_report.json
```

Query (online, tất định, tối đa 2 lượt LLM):

```
router (regex → kNN intents)
  ├─ qa   : retrieve(BM25 ⊕ dense) → OOS → expand → LLM → guard → retry 1 → extractive
  ├─ calc : slots → hỏi lại nếu thiếu slot → tool Decimal → kiểm tra giả định sai → diễn đạt → guard
  └─ oos  : từ chối kèm lý do
```

## 5. Mô hình dữ liệu

Node (Pydantic, `src/common/schema.py`):

- `node_id, doc_id, level ∈ {chapter, section, article, clause, point, table}, path[], article, clause, point`
- `text, lead_in, parent_id, children[], refs[], external_refs[], has_exception`
- `effective_from, effective_to, status ∈ {active, superseded, repealed}, version`
- `table_md, page_span[start,end], amend_notes[]`

`node_id` = `{doc_id}:D{article}[.K{clause}[.{point}]]`

- Ví dụ: `45-2019-QH14:D98.K1.a`, `45-2019-QH14:D10a`, `45-2019-QH14:D98.K1.đ`
- `article` khớp `\d+[a-zđ]?`; `point` khớp `[abcdđeghiklmnopqrstuvxy]`
- Chương/Mục: `{doc_id}:C{roman}` và `{doc_id}:C{roman}.M{n}`; bảng: `{parent_id}.T{n}`
- `make_node_id` / `parse_node_id` phải round-trip chính xác.

## 6. Ingest

### 6.1 OCR

```bash
ocrmypdf -l vie --rotate-pages --deskew --clean --jobs 4 \
  --sidecar <out>.txt <in>.pdf <out>-ocr.pdf
```

- Nếu < 95% trang đạt (≥ 50 ký tự) thì chạy lại với `--oversample 300`, rồi báo số liệu **cả hai** lần chạy.
- Output rà soát cho người dùng: `data/raw/<doc>-ocr.pdf` (bôi đen + Ctrl+F được),
  `data/raw/<doc>.txt`, và `data/raw/review/<doc>.md` (mỗi trang bắt đầu bằng `=== Trang N ===`). Tất cả gitignored.
- Không sửa tay file `.txt` (loader đọc `*-ocr.pdf`, không đọc `.txt`). Lỗi OCR lẻ tẻ xử lý bằng
  `config/ocr_fixes.yaml` có version để build vẫn tất định.

### 6.2 Chuẩn hóa text

NFC → thống nhất vị trí dấu thanh (hòa/hoà về một kiểu) → chuẩn hóa khoảng trắng → `strip_diacritics` (đ/Đ → d/D).

### 6.3 Regex nhận dạng cấu trúc (áp lên dòng đã chuẩn hóa, khớp ở đầu dòng)

| Cấp | Pattern | Ghi chú |
|---|---|---|
| Chương | `^Chương\s+([IVXLC]+)\b` | tiêu đề có thể nằm ở dòng sau |
| Mục | `^Mục\s+(\d+)\b` | |
| Điều | `^Điều\s+(\d+[a-zđ]?)\.\s*` | `article` giữ nguyên hậu tố, vd `2a` |
| Khoản | `^(\d+)\.\s` | chỉ tìm trong phạm vi một Điều |
| Điểm | `^([abcdđeghiklmnopqrstuvxy])\)\s` | chỉ tìm trong phạm vi một Khoản; luôn kèm `lead_in` của Khoản cha |
| Bảng | dòng có ≥ 2 cột tách bằng ≥ 2 khoảng trắng / đường kẻ | `table_md` + text làm phẳng |

- Chỉ nhận là tiêu đề Điều khi số Điều **tăng liên tục** so với Điều trước; trường hợp khác ghi vào report
  (chống nhầm dòng "Điều" nằm giữa nội dung).
- Cắt bỏ phần sau Điều cuối cùng (Nơi nhận, chữ ký, mục lục cuối văn bản).

### 6.4 Tham chiếu

- Resolve được: `điểm x khoản y Điều z`, `khoản y Điều này`, `Điều này`, `Bộ luật này`.
- Tham chiếu tới văn bản khác → `external_refs` (không resolve, không bịa nội dung).

### 6.5 has_exception

Pattern: `ngoại trừ|trừ trường hợp|trừ khi|(?<!khấu )\btrừ\b|không áp dụng`.

- Cụm "khấu trừ" (Điều 102) phải cho `False`. Có test âm tính.

### 6.6 Bảng

- `table_md`: Markdown nguyên bảng. `text`: làm phẳng theo hàng `"cột: giá trị; …"`.
- Mỗi bảng là node `level=table`, `node_id={parent_id}.T{n}`, kèm `page_span`.

### 6.7 Vòng đời văn bản

- `filter_active(nodes, as_of)` giữ node thỏa `effective_from <= as_of < effective_to` (`effective_to=None` = vô hạn).
- `status=superseded` thì trả kèm cảnh báo cho người dùng.
- Mỗi phiên bản văn bản là một `doc_id` riêng. Index mặc định chỉ chứa văn bản active tại `as_of`.

### 6.8 Tất định và đối chiếu chéo

- Sort theo `node_id`, `json.dumps(..., sort_keys=True, ensure_ascii=False)`. Hai lần chạy phải cho cùng sha256.
- Đối chiếu chéo: với mỗi Điều có ở cả hai bản, tính độ giống (`difflib.SequenceMatcher`).
  Điều có độ giống < 0.97 được liệt kê trong report: mỗi Điều trong danh sách hoặc **đã sửa đổi thật**,
  hoặc **bị lỗi OCR** — đây là danh sách ưu tiên để người dùng rà soát.

## 7. Truy xuất

- **Tokenize**: tách theo âm tiết, lowercase. Giữ nguyên token đặc biệt `45/2019/qh14`, `dieu_98`, `khoan_1`.
  Mở rộng truy vấn bằng `config/synonyms.yaml`.
- **BM25** (`bm25s`): 2 trường (có dấu, bỏ dấu), `score = s_acc + s_noacc`.
- **Chunk**: index ở mức leaf (Điểm > Khoản > Điều), `text = lead_in + text`.
  `header_mode ∈ {none, true, placebo}`; `placebo` lấy path của một Điều khác theo seed.
- **Dense** (`sentence-transformers`): `multilingual-e5-large` (prefix `query: ` / `passage: `) và `bge-m3` (không prefix).
  Dự phòng `EmbeddingGemma-300m` (prompt theo model card). Vector normalize, lưu `.npy` + meta
  `{model, revision, chunk_sha, n_truncated}`. Tìm kiếm bằng numpy brute-force (không dùng FAISS).
- **Fusion**: `fused = α·dense + (1-α)·bm25`, α₀ = 0.7, chuẩn hóa min-max theo truy vấn (có thử z-score).
  Tập ứng viên = hợp top-100 của hai phía; phía thiếu ứng viên nhận điểm min của list đó.
  RRF (c=60) chỉ là cột đối chứng. α chỉ tune trên dev.
- **Retriever**: mode `bm25 | dense | linear | rrf`; lọc theo `as_of`; trả kèm `raw_dense`, `raw_bm25`
  (và `raw_rerank` nếu có) để guard/OOS dùng điểm thô.
- **Expand**: thêm Điều cha, các Khoản `has_exception` cùng Điều, cross-ref 1 hop với tập `visited`,
  giới hạn ngân sách token.
- **OOS**: ngưỡng đặt trên **điểm thô** (cosine top-1, BM25 thô, logit reranker), không dùng điểm fused.
  Hiệu chỉnh riêng từng cấu hình trên dev → `config/thresholds.yaml`.
- **Reranker**: chỉ bật khi CI95 của paired Δ nDCG@10 > 0 **và** p95 tăng ≤ 1 s.

## 8. Guard

1. Mọi `[[node_id]]` trong câu trả lời phải thuộc tập đã truy xuất.
2. Cấm gõ tự do `"Điều N"` ngoài cú pháp `[[...]]`.
3. Mọi số / % / ngày phải thuộc: số trong chunk được trích ∪ output tool ∪ câu hỏi.
   Chuẩn hóa trước khi so: `"1.000.000"`, `"1,5"`, `"150 %"`, `"01/01/2021"`, `"ngày 1 tháng 1 năm 2021"`.
4. Mỗi câu khẳng định phải có ≥ 1 trích dẫn; whitelist câu meta và câu từ chối.
   Bộ tách câu phải giữ nguyên `"1.000.000"`, `"v.v."`, `"TP."`.

Xử lý fail: sinh thông báo lỗi cụ thể → retry **1 lần** → `extractive_fallback` (trích nguyên văn chunk top-k kèm trích dẫn).

Render trích dẫn: `[Bộ luật Lao động 2019, Điều 98, Khoản 1, Điểm a]`.

## 9. Agent và tool

- **LLM client**: OpenAI-compatible (gói `openai`), `base_url` từ `config/llm.yaml`, key từ ENV.
  Timeout, backoff khi 429. Chuỗi fallback A → B → extractive. `FakeLLM` chạy theo kịch bản để test.
- **Ngân sách**: ≤ 2 lượt LLM / truy vấn. Nếu đã dùng LLM để trích slot thì khi guard fail trả template, **không retry**.
- **Router**: regex trước, sau đó kNN trên ví dụ trong `config/intents.yaml`.
  Intent: `qa`, `calc_overtime`, `calc_leave`, `oos`.
- **Slots**: regex → Pydantic; thiếu slot thì sinh câu hỏi lại; LLM JSON fallback phải qua validate.
- **Tool**: tính bằng `Decimal` (quantize về đồng, `ROUND_HALF_UP`). Parse được `"5 triệu"`, `"5.000.000đ"`, `"5tr"`.
  - `overtime`: input `{hourly_wage, hours, day_type, night}`; output breakdown + `source_node_ids` + nhãn "mức tối thiểu".
  - `annual_leave`: input `{months_worked, job_category, years_of_service}`; output số ngày + nguồn.
    Phép năm theo tỷ lệ trả `Decimal` **chưa làm tròn**, kèm ghi chú.
- **rules/*.yaml**: `{key, value, unit, source_node_id, evidence, kind: minimum|exact}`.
  Test bắt buộc: `evidence ⊂ text` của node và `str(value) ⊂ evidence`.
  Giá trị không tìm thấy câu trích dẫn trong văn bản **không được** đưa vào rule.
- **Kiểm tra giả định sai**: nếu số trong câu hỏi mâu thuẫn với chunk thì trả lời sửa lại giả định.

## 10. API và UI

- **FastAPI**: `GET /health`, `POST /ask`, `POST /calc/overtime`, `POST /calc/leave` (dùng chung `core.answer`).
- **UI Gradio Spaces**: hiển thị câu trả lời + danh sách trích dẫn + trạng thái guard/OOS.
  Không upload PDF luật lên Space (không public dữ liệu).
- **Deploy**: `Dockerfile` (CPU, model đóng băng trong image), `.github/workflows/ci.yml`, `deploy.md`
  hướng dẫn chạy trên HF Spaces. Ollama chạy local, không đóng gói trong image.

## 11. Đánh giá và số liệu bắt buộc

- **Tập đánh giá**:
  - `qa_eval.jsonl`: 200 câu, `answerable` 80 % (160) / `unanswerable` 20 % (40), id dạng `qa-001`.
    - 60 % (120) có câu hỏi bám điều khoản cụ thể. 40 % (80) viết tự nhiên, `match_regex` mức Điều.
    - `type`: `point_qa` 30 % (60), `clause_qa` 40 % (80), `table` 10 % (20), `multi_hop` 20 % (40).
  - `calc_eval.jsonl`: 30 case. `overtime` 15, `annual_leave` 15, và `0 < refusal` ≤ 3 case có giả định sai.
- **Protocol (cố định)**:
  - Index = văn bản mặc định; bỏ 20 % chunk ngẫu nhiên theo seed 42; câu hỏi gold thuộc phần còn lại.
  - Dev/test split 50/50 theo điều khoản gold để chống rò rỉ. Tune chỉ trên dev, test chốt một lần.
- **Metrics**: P@5, Recall@10, nDCG@10, MRR@10; CI95 bằng bootstrap (1 000 mẫu, seed 42) cho nDCG@10;
  paired diff trên cùng `qid`. Cho **cả 3 tầng chunk** (leaf / clause / article) để chứng minh chọn leaf là tốt nhất.
- **Ablation bắt buộc** (báo cáo thật, không làm đẹp):
  - BM25 vs dense vs linear (α = 0.0 → 1.0 bước 0.1) vs RRF.
  - `header_mode`: none vs true vs placebo.
  - Bỏ `strip_diacritics` (có dấu vs 2 trường).
  - Retrieval-only vs QA vs QA + guard; `max_baseline_len` (512 ký tự) để so với baseline cắt văn bản.
  - OOS: bảng ngưỡng ↔ FPR. Cross-tab 2×2 "có gold chunk trong top-1 × hệ thống nói OOS".
- **Kiểm tra chất lượng câu trả lời**:
  - `judge_pass` (0–1) + `needs_multi_hop` (bool) + `min_expected_cites` (int), gán bởi `eval/llm_select/` (offline).
  - `cite_precision`, `gold_cited`, `numeric_mismatch` do **code** tính — không giao cho người/LLM chấm.
  - `faithfulness_judge` và `answer_correctness_judge` bằng LLM **khác họ** với generator (ma trận,
    log `judge_model` + `judge_asr`); α ước lượng được trên 60 mẫu.

## 12. Ràng buộc chất lượng dữ liệu

- Không đoán số điều, số khoản của bản hợp nhất, ngày hiệu lực, hay nguồn tải PDF.
  Mọi giá trị phải có **câu trích dẫn** trong text OCR và lưu ở `data/ingest_report.json`.
- Ngày dương lịch viết là `2021-01-01`; tháng dương lịch viết `2021-01`; không dùng `dd/mm/yyyy` trong tài liệu kỹ thuật.
- `as_of` mặc định = ngày index được build; câu hỏi "còn hiệu lực không" trả theo `as_of`, không theo "hôm nay" mơ hồ.
- Mọi con số trong `README.md`, `docs/checkpoints/*.md` phải copy từ `results/*.json`; kèm timestamp + sha256 của node set.

### 12.1 Các mặc định đã chốt (trước đây là câu hỏi mở)

| Vấn đề | Mặc định chốt | Cách xử lý minh bạch |
|---|---|---|
| Tác giả golden set | Agent sinh bằng LLM + tự curate, không có người viết tay | `author` gán `llm`, `verified_by: agent`. Tỷ lệ người-viết = 0 %, ghi rõ trong README |
| Chấm "trung thực" thủ công | Tự động bằng LLM judge khác họ + kiểm tra số liệu bằng code | Bảng so khớp 30 câu ghi vào `docs/checkpoints/`, người dùng spot-check tùy ý |
| Giá trị pháp lý trong `rules/` | Trích nguyên văn từ OCR, test `evidence ⊂ text` | Mọi giá trị kèm câu trích; không tìm được trích thì bỏ rule |
| GPU 4 GB | Embed query trên CPU; không nạp 3 model cùng lúc | Nếu CUDA OOM, fallback CPU; ghi thời gian thật |
| LLM | Ollama local (`qwen2.5:7b-instruct`) hoặc API hợp lệ; tắt = `extractive` | `docs/FINAL_REPORT.md` ghi model/nguồn đã dùng |
| Deploy | Giao `Dockerfile` + HF Spaces config; không deploy hộ | `deploy.md` mô tả cách chạy; nếu không tạo HF token thì nêu rõ |
| Ngưỡng OOS | Hiệu chỉnh tối ưu trên dev, tiêu chí chọn: khoảng cách lớn nhất giữa 2 phân bố | Bảng ngưỡng ↔ FPR trong report |
| Giả định mặc định của tool | Công khai trong `docs/FINAL_REPORT.md`, thời gian làm 1 năm = 12 tháng | Ghi nhãn "mức tối thiểu" và công bố giả định |
| Ngôn ngữ sản phẩm | Tiếng Việt cho UI, câu trả lời, report; code/commit tiếng Anh | — |