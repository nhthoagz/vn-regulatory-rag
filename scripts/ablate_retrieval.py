"""Ablation retrieval trên chunk lá: bm25 / dense / linear / rrf cho từng model (SPEC §11).

Ghi `results/retrieval_ablation.json`. Chạy sau khi đã `python -m scripts.fetch_models`,
và nên chạy bằng nohup vì embedding CPU khá lâu.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from scripts.eval import load_jsonl, ndcg_at_k, sha256_file
from src.common.paths import EVAL_DIR, INDEX_DIR, PROCESSED_DIR, REPO_ROOT, RESULTS_DIR
from src.retrieval.bm25 import BM25Index
from src.retrieval.dense import DenseIndex
from src.retrieval.hybrid import linear_fuse, rrf_fuse

MODES = ("bm25", "dense", "linear", "rrf")


def metrics(rankings: list[list[str]], golds: list[set[str]]) -> dict[str, float]:
    precision = ndcg = mrr = recall = 0.0
    for ranked, gold in zip(rankings, golds, strict=True):
        precision += len(gold.intersection(ranked[:5])) / 5
        recall += len(gold.intersection(ranked)) / len(gold) if gold else 0.0
        ndcg += ndcg_at_k(ranked, gold, 10)
        mrr += next((1 / (i + 1) for i, node_id in enumerate(ranked) if node_id in gold), 0.0)
    count = len(rankings) or 1
    return {
        "items": len(rankings),
        "p_at_5": round(precision / count, 4),
        "recall_at_10": round(recall / count, 4),
        "ndcg_at_10": round(ndcg / count, 4),
        "mrr_at_10": round(mrr / count, 4),
    }


def main(argv: list[str] | None = None) -> int:
    models = argv or ["bge-m3", "e5-large"]
    chunks = load_jsonl(PROCESSED_DIR / "chunks_leaf.jsonl")
    qa = load_jsonl(EVAL_DIR / "qa_eval.jsonl")
    items = [item for item in qa if item["type"] != "oos"]
    queries = [item["question"] for item in items]
    golds = [set(item["gold_node_ids"]) for item in items]
    chunk_sha = sha256_file(PROCESSED_DIR / "chunks_leaf.jsonl")

    bm25 = BM25Index().fit([chunk["text"] for chunk in chunks])

    def bm25_scores(query: str) -> dict[int, float]:
        scored = ((i, bm25.score_doc(query, i)) for i in range(bm25.doc_count))
        return {index: score for index, score in scored if score > 0}

    bm_scores = [bm25_scores(query) for query in queries]

    def to_ranked(pairs: list[tuple[int, float]]) -> list[str]:
        return [chunks[index]["node_id"] for index, _ in pairs]

    report: dict = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tier": "leaf",
        "chunks": len(chunks),
        "chunks_sha256": chunk_sha,
        "qa_sha256": sha256_file(EVAL_DIR / "qa_eval.jsonl"),
        "items": len(items),
        "results": {},
    }
    bm_rankings = [to_ranked(sorted(score.items(), key=lambda x: x[1], reverse=True)[:10])
                   for score in bm_scores]
    report["results"]["bm25"] = metrics(bm_rankings, golds)
    print("bm25", report["results"]["bm25"], flush=True)

    for key in models:
        print(f"build dense {key} ...", flush=True)
        dense = DenseIndex.build(
            texts=[chunk["text"] for chunk in chunks],
            chunk_ids=[chunk["node_id"] for chunk in chunks],
            model_key=key,
            chunk_sha=chunk_sha,
            cache_dir=INDEX_DIR,
        )
        hits = dense.search_batch(queries, top_k=20)
        dense_scores = [dict(h) for h in hits]
        entry = {"truncated": dense.truncated, "dim": int(dense.embeddings.shape[1])}

        def ranked_from(scores: dict[int, float]) -> list[str]:
            ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:10]
            return [chunks[index]["node_id"] for index, _ in ordered]

        entry["dense"] = metrics([ranked_from(s) for s in dense_scores], golds)
        entry["linear"] = metrics(
            [to_ranked(linear_fuse(bm, dn, 0.5)[:10]) for bm, dn in zip(bm_scores, dense_scores,
                                                                       strict=True)],
            golds,
        )
        entry["rrf"] = metrics(
            [
                to_ranked(
                    rrf_fuse(
                        [
                            [i for i, _ in sorted(bm.items(), key=lambda x: x[1], reverse=True)],
                            [i for i, _ in sorted(dn.items(), key=lambda x: x[1], reverse=True)],
                        ]
                    )[:10]
                )
                for bm, dn in zip(bm_scores, dense_scores, strict=True)
            ],
            golds,
        )
        report["results"][key] = entry
        for mode in ("dense", "linear", "rrf"):
            print(f"{key}/{mode}", entry[mode], flush=True)

    path = RESULTS_DIR / "retrieval_ablation.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(f"report: {path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
