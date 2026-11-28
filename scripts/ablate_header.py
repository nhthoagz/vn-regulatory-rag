"""Ablation header trích dẫn: true / none / placebo trên BM25 (SPEC §11).

Không cần model. Chỉ thay phần header của chunk lá đã build (giữ nguyên thân chunk), nên đo
đúng tác động của việc "nhét nhãn Điều/Khoản" vào text được index.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import UTC, datetime

from scripts.eval import load_jsonl, ndcg_at_k, sha256_file
from src.common.paths import EVAL_DIR, PROCESSED_DIR, REPO_ROOT, RESULTS_DIR
from src.retrieval.bm25 import BM25Index

MODES = ("true", "none", "placebo")


def strip_header(text: str) -> str:
    first, _, rest = text.partition("\n")
    return rest if first.startswith("[") and rest else text


def placebo_text(text: str, citation: str, pool: list[str], node_id: str) -> str:
    index = int(hashlib.sha256(node_id.encode("utf-8")).hexdigest()[:8], 16) % len(pool)
    return text.replace(citation, pool[index], 1)


def variants(chunks: list[dict]) -> dict[str, list[str]]:
    pool = [chunk["citation"] for chunk in chunks]
    result: dict[str, list[str]] = {mode: [] for mode in MODES}
    for chunk in chunks:
        text = chunk["text"]
        result["true"].append(text)
        result["none"].append(strip_header(text))
        result["placebo"].append(placebo_text(text, chunk["citation"], pool, chunk["node_id"]))
    return result


def evaluate(chunks: list[dict], texts: list[str], qa: list[dict], split: str) -> dict:
    index = BM25Index().fit(texts)
    items = [
        item for item in qa if item["type"] != "oos" and (split == "all" or item["split"] == split)
    ]
    precision = ndcg = mrr = 0.0
    for item in items:
        gold = set(item["gold_node_ids"])
        hits = index.search(item["question"], top_k=10)
        ranked = [chunks[hit.index]["node_id"] for hit in hits]
        precision += len(gold.intersection(ranked[:5])) / 5
        ndcg += ndcg_at_k(ranked, gold, 10)
        mrr += next((1 / (i + 1) for i, node_id in enumerate(ranked) if node_id in gold), 0.0)
    count = len(items) or 1
    return {
        "items": len(items),
        "p_at_5": round(precision / count, 4),
        "ndcg_at_10": round(ndcg / count, 4),
        "mrr_at_10": round(mrr / count, 4),
    }


def main(argv: list[str] | None = None) -> int:
    split = sys.argv[1] if len(argv or sys.argv) > 1 else "all"
    chunks = load_jsonl(PROCESSED_DIR / "chunks_leaf.jsonl")
    qa = load_jsonl(EVAL_DIR / "qa_eval.jsonl")
    texts = variants(chunks)
    rows = {mode: evaluate(chunks, texts[mode], qa, split) for mode in MODES}
    report = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "split": split,
        "chunks": len(chunks),
        "chunks_sha256": sha256_file(PROCESSED_DIR / "chunks_leaf.jsonl"),
        "qa_sha256": sha256_file(EVAL_DIR / "qa_eval.jsonl"),
        "modes": rows,
        "note": "header placebo dùng nhãn của chunk khác cùng văn bản, chọn tất định theo node_id",
    }
    path = RESULTS_DIR / "header_ablation.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    for mode in MODES:
        row = rows[mode]
        print(f"header={mode}: P@5={row['p_at_5']} nDCG@10={row['ndcg_at_10']} "
              f"MRR@10={row['mrr_at_10']}")
    print(f"report: {path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
