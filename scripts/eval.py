"""Chấm điểm retrieval và câu trả lời trên bộ đề đã sinh (SPEC §11).

Chỉ dùng artifact local, không gọi model/LLM. Kết quả ghi `results/eval_report.json` và
mọi con số trong tài liệu phải copy từ file này.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.common.paths import EVAL_DIR, INDEX_DIR, PROCESSED_DIR, REPO_ROOT, RESULTS_DIR
from src.core.pipeline import Pipeline
from src.retrieval.bm25 import BM25Index

DEFAULT_DOC = "18-VBHN-VPQH-2026"
TIERS = ("leaf", "clause", "article")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dcg(relevances: list[int]) -> float:
    return sum(rel / math.log2(index + 2) for index, rel in enumerate(relevances))


def ndcg_at_k(ranked: list[str], gold: set[str], k: int = 10) -> float:
    if not gold:
        return 0.0
    gains = [1 if node_id in gold else 0 for node_id in ranked[:k]]
    best = dcg([1] * min(len(gold), k))
    return dcg(gains) / best if best else 0.0


def tier_gold(nodes: dict[str, dict], gold_ids: list[str], tier: str) -> set[str]:
    """Gold ở tầng khoản/điều: tổ tiên ở đúng tầng của các node lá trong gold."""
    if tier == "leaf":
        return set(gold_ids)
    result: set[str] = set()
    for gold in gold_ids:
        current = nodes.get(gold)
        while current is not None:
            if current["level"] == tier:
                result.add(current["node_id"])
                break
            if not current.get("parent_id"):
                break
            current = nodes.get(current["parent_id"])
    return result


def evaluate_retrieval(tier: str, qa: list[dict], split: str) -> dict[str, Any]:
    """P@5, Recall@10, nDCG@10, MRR@10 của BM25 trên một tầng chunk."""
    chunks = load_jsonl(PROCESSED_DIR / f"chunks_{tier}.jsonl")
    nodes = {node["node_id"]: node for node in load_jsonl(PROCESSED_DIR / "nodes.jsonl")}
    index = BM25Index().fit([chunk["text"] for chunk in chunks])
    items = [
        item for item in qa if item["type"] != "oos" and (split == "all" or item["split"] == split)
    ]
    precision = recall = ndcg = mrr = 0.0
    for item in items:
        gold = tier_gold(nodes, item["gold_node_ids"], tier)
        hits = index.search(item["question"], top_k=10)
        ranked = [chunks[hit.index]["node_id"] for hit in hits]
        precision += len(gold.intersection(ranked[:5])) / 5
        recall += len(gold.intersection(ranked)) / len(gold) if gold else 0.0
        ndcg += ndcg_at_k(ranked, gold, 10)
        mrr += next((1 / (i + 1) for i, node_id in enumerate(ranked) if node_id in gold), 0.0)
    count = len(items) or 1
    return {
        "tier": tier,
        "split": split,
        "items": len(items),
        "chunks": len(chunks),
        "p_at_5": round(precision / count, 4),
        "recall_at_10": round(recall / count, 4),
        "ndcg_at_10": round(ndcg / count, 4),
        "mrr_at_10": round(mrr / count, 4),
    }


def evaluate_answers(
    qa: list[dict], calc: list[dict], split: str, coverage: float = 0.5
) -> dict[str, Any]:
    """Chạy pipeline trên bộ đề: độ chính xác theo loại, vi phạm guard, độ đúng của calc."""
    pipeline = Pipeline(
        chunks_path=PROCESSED_DIR / "chunks_leaf.jsonl",
        nodes_path=PROCESSED_DIR / "nodes.jsonl",
        fallback_path=INDEX_DIR / "fallback_map.json",
        default_doc_id=DEFAULT_DOC,
        coverage_threshold=coverage,
    )
    per_type: dict[str, dict[str, float]] = {}
    violations = 0
    samples: list[dict] = []
    for item in qa:
        if split != "all" and item["split"] != split:
            continue
        answer = pipeline.ask(item["question"])
        if answer.violations and len(samples) < 5:
            samples.append(
                {
                    "qid": item["qid"],
                    "type": item["type"],
                    "violations": answer.violations,
                    "answer": answer.answer[:200],
                }
            )
        bucket = per_type.setdefault(item["type"], {"items": 0, "correct": 0, "gold_cited": 0})
        bucket["items"] += 1
        violations += len(answer.violations)
        gold = set(item["gold_node_ids"])
        if item.get("expect_refusal"):
            bucket["correct"] += int(answer.refused)
            continue
        cited = bool(gold.intersection(answer.node_ids))
        bucket["gold_cited"] += int(cited)
        if item.get("expect_warning"):
            bucket["correct"] += int(bool(answer.warnings) and cited)
        else:
            bucket["correct"] += int(cited)

    calc_correct = 0
    calc_items = [case for case in calc if split == "all" or case["split"] == split]
    for case in calc_items:
        answer = pipeline.ask(case["question"])
        output = answer.tool_output or {}
        value = output.get("amount", output.get("days"))
        expected = case.get("expected_amount", case.get("expected_days"))
        calc_correct += int(value == expected)

    return {
        "split": split,
        "violations": violations,
        "violation_samples": samples,
        "calc_correct": calc_correct,
        "calc_items": len(calc_items),
        "types": {
            name: {
                **bucket,
                "accuracy": (
                    round(bucket["correct"] / bucket["items"], 4) if bucket["items"] else 0.0
                ),
            }
            for name, bucket in sorted(per_type.items())
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=RESULTS_DIR / "eval_report.json")
    parser.add_argument("--split", choices=("dev", "test", "all"), default="all")
    parser.add_argument(
        "--coverage", type=float, default=0.5, help="ngưỡng IDF coverage để từ chối"
    )
    args = parser.parse_args(argv)

    qa_path = EVAL_DIR / "qa_eval.jsonl"
    calc_path = EVAL_DIR / "calc_eval.jsonl"
    qa = load_jsonl(qa_path)
    calc = load_jsonl(calc_path)
    retrieval = [evaluate_retrieval(tier, qa, args.split) for tier in TIERS]
    answers = evaluate_answers(qa, calc, args.split, coverage=args.coverage)

    report = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "split": args.split,
        "inputs": {
            "qa_eval": sha256_file(qa_path),
            "calc_eval": sha256_file(calc_path),
            "chunks_leaf": sha256_file(PROCESSED_DIR / "chunks_leaf.jsonl"),
        },
        "retrieval": retrieval,
        "answers": answers,
        "config": {
            "dense": "unavailable",
            "reranker": "unavailable",
            "llm": "unavailable",
            "coverage_threshold": args.coverage,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for row in retrieval:
        print(
            f"{row['tier']}: P@5={row['p_at_5']} R@10={row['recall_at_10']} "
            f"nDCG@10={row['ndcg_at_10']} MRR@10={row['mrr_at_10']} ({row['items']} câu)"
        )
    print(f"answers: violations={answers['violations']}")
    for name, bucket in answers["types"].items():
        print(f"  {name}: accuracy={bucket['accuracy']} ({bucket['items']} câu)")
    print(f"calc: {answers['calc_correct']}/{answers['calc_items']}")
    try:
        shown = args.report.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        shown = args.report.as_posix()
    print(f"report: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())