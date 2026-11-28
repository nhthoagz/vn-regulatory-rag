# Deploy & vận hành

## 1. Chuẩn bị (một lần)

```bash
uv venv ~/.venvs/vn-rag --python 3.11
uv pip install --python ~/.venvs/vn-rag/bin/python -e .
make ocr        # nếu chưa có data/raw/*-ocr.pdf
make build      # nodes.jsonl, chunks_*.jsonl, fallback_map.json, ingest_report.json
make rules      # rules/*.yaml có evidence nguyên văn
make golden && make eval
```

`rules/`, `data/processed/`, `data/index/`, `data/ingest_report.json` **không nằm trong git**
(chứa text luật — rule 4). Trên máy mới phải chạy `make rules && make build` trước khi phục vụ.

## 2. Chạy API

```bash
make serve                      # http://127.0.0.1:8000/docs
curl -s localhost:8000/health
curl -s -X POST localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"Điều 98 quy định mức lương làm thêm giờ thế nào?"}'
curl -s -X POST localhost:8000/calc/overtime -H 'content-type: application/json' \
  -d '{"hourly_wage":"50000","hours":"4","kind":"weekday"}'
```

`/ask` nhận `mode` ∈ `bm25|dense|linear|rrf`; `dense/linear/rrf` cần cài extra `ml`
(`uv pip install -e .[ml]`), đã tải model (`python -m scripts.fetch_models`) và có cache dense.
Mode mặc định `bm25` không cần model.

## 3. Docker

```bash
make build && make rules         # artifact phải có trước khi build image
docker build -t vn-rag:0.1 .
docker run --rm -p 8000:8000 vn-rag:0.1
```

## 4. Biến môi trường

| Biến | Ý nghĩa |
|---|---|
| `DENSE_MODEL` | `bge-m3` (mặc định) hoặc `e5-large`, dùng khi `mode != bm25` |
| `EMBED_THREADS` | số thread CPU khi embed (mặc định 4) |
| `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `LLM_MODEL` | bật lớp LLM tuỳ chọn; thiếu thì trả lời extractive |
| `HF_HOME` | cache model (mặc định `~/.cache/huggingface`) |

## 5. Kiểm tra sức khoẻ & bất biến

```bash
make lint && make leak
uv run pytest -m "not realdata"           # nhanh, không cần PDF/model
uv run pytest -m realdata                 # cần PDF đã OCR
python -m scripts.parse_stats             # số ingest + bất biến node_id
python -m scripts.eval --split all --coverage 0.85
```

## 6. Giới hạn đã biết

- Bản hợp nhất thiếu Điều 76–79 (mất trang in 33–34) → trả từ bản gốc kèm cảnh báo bắt buộc.
- Không có dense/reranker/LLM trong CI: CI chỉ chạy test không cần model.
- Docker/CI mới ở mức file, chưa chạy trên hạ tầng thật (docker chưa cài trên máy phát triển).
