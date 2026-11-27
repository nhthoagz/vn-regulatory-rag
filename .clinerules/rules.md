# Quy tắc dự án vn-regulatory-rag

## 1. Không bịa số liệu
- Mọi con số trong `README.md`, `docs/*.md`, `docs/checkpoints/*.md` phải copy từ `results/*.json` hoặc
  `data/ingest_report.json`, kèm timestamp và sha256 của artifact.
- Script fail hoặc cho số liệu lạ: báo đúng giá trị và log, không sửa tay cho đẹp.
- Số liệu pháp lý (mức %, số ngày, ngày hiệu lực) chỉ vào `rules/*.yaml` khi có câu trích nguyên văn
  trong `nodes.jsonl`; test phải kiểm `evidence ⊂ node.text`.

## 2. Môi trường
- WSL2 Ubuntu, Python 3.11 qua `uv`, venv `~/.venvs/vn-rag`, `HF_HOME=~/.cache/huggingface`.
- Không đặt cache model hay dữ liệu lớn trên `/mnt/e`; repo có thể nằm trên `/mnt/e` vì dữ liệu nhỏ.
- GPU 4 GB VRAM: chỉ nạp một model một lúc, embed query trên CPU; OOM thì fallback CPU và ghi thời gian thật.
- Secrets chỉ trong `.env`; `config/llm.yaml` chỉ ghi tên biến ENV.

## 3. Job dài
- Mọi lệnh > 60 s (OCR, index, embedding, ablation) chạy `nohup ... > logs/<task>.log 2>&1 &`.
- Theo dõi bằng `tail -n 30 logs/<task>.log`, `ps aux`, `nvidia-smi`, `free -g` tới khi xong.

## 4. Workflow
- Một task mỗi lần theo `PLAN.md` §4. Task xong khi `make t T=<path>` exit 0 **và** `ruff check .` exit 0.
- Commit conventional sau mỗi task đã pass; tag `cpN-<slug>` ở mỗi checkpoint.
- Circuit breaker: cùng một lỗi lặp 3 lần thì dừng, tóm tắt log, hỏi người dùng.
- Không đẩy PDF luật, text luật, `.env`, model weights lên repo (kể cả repo public).

## 5. Rà soát trước khi báo xong
- Chạy lại lệnh verify 2 lần (kết quả phải giống nhau), đọc `git status`, kiểm diff, đọc output thật.
- Không kết luận "đã xong" dựa trên việc script không báo lỗi; phải có artifact cụ thể để chỉ ra.