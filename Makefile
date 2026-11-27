export UV_PROJECT_ENVIRONMENT := $(HOME)/.venvs/vn-rag
export HF_HOME := $(HOME)/.cache/huggingface
export PYTHONUTF8 := 1

UV ?= uv
T ?=

.PHONY: dirs setup lint leak parse-stats test t check ocr ocr-force ocr-best ocr-metrics

OCR_JOBS ?= 4
TESSDATA_BEST ?= $(HOME)/.local/share/tessdata_best

dirs:
	mkdir -p data/raw data/processed data/index logs results

setup: dirs
	$(UV) python pin 3.11
	$(UV) sync

lint:
	$(UV) run ruff check .

leak:
	$(UV) run python -m scripts.check_leak

parse-stats:
	$(UV) run python -m scripts.parse_stats

test:
	$(UV) run pytest

t:
	$(UV) run pytest -q $(T)

check: lint leak
	$(UV) run pytest -m "not realdata and not model and not llm"

ocr:
	$(UV) run python -m scripts.ocr --jobs $(OCR_JOBS)

ocr-force:
	$(UV) run python -m scripts.ocr --force --jobs $(OCR_JOBS)

ocr-best:
	$(UV) run python -m scripts.ocr --force --suffix=-best \
		--tessdata-dir $(TESSDATA_BEST) --jobs $(OCR_JOBS)

ocr-metrics:
	$(UV) run python -m scripts.ocr_metrics data/raw/*.txt