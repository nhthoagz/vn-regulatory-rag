"""Ghi thống kê parse của từng văn bản vào `results/parse_stats.json`.

Mọi con số về số Chương/Điều/Khoản/Điểm ghi trong tài liệu phải copy từ artifact này
(SPEC §12), không lấy từ trí nhớ của người viết.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.common.config import DocumentMeta, load_documents
from src.common.paths import RAW_DIR, REPO_ROOT, RESULTS_DIR
from src.ingest.loader import load_pages
from src.ingest.parser import ParseResult, parse_pages

REPORT_PATH = RESULTS_DIR / "parse_stats.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def summarize(
    doc: DocumentMeta,
    result: ParseResult,
    *,
    pdf: str,
    pdf_sha256: str,
    pages: int,
) -> dict[str, Any]:
    """Tóm tắt một lần parse: số liệu, Điều thiếu, cảnh báo, bất biến node_id."""
    ids = [node.node_id for node in result.nodes]
    counts = Counter((issue.kind, issue.severity) for issue in result.issues)
    return {
        "doc_id": doc.doc_id,
        "role": doc.role,
        "pdf": pdf,
        "pdf_sha256": pdf_sha256,
        "pages": pages,
        "node_count": len(ids),
        "node_id_unique": len(ids) == len(set(ids)),
        "missing_articles": list(result.missing_articles),
        "stats": dict(sorted(result.stats.items())),
        "issues": [
            {"kind": kind, "severity": severity, "count": count}
            for (kind, severity), count in sorted(counts.items())
        ],
        "errors": [
            {"kind": issue.kind, "page": issue.page, "message": issue.message}
            for issue in result.issues
            if issue.severity == "error"
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--only", action="append", metavar="DOC_ID")
    args = parser.parse_args(argv)

    documents = load_documents()
    if args.only:
        wanted = set(args.only)
        documents = [doc for doc in documents if doc.doc_id in wanted]
        if not documents:
            return 2

    entries: list[dict[str, Any]] = []
    for doc in documents:
        pdf_path = RAW_DIR / f"{Path(doc.file).stem}-ocr.pdf"
        if not pdf_path.is_file():
            entries.append({"doc_id": doc.doc_id, "error": f"missing {pdf_path.name}"})
            continue
        loaded = load_pages(pdf_path)
        result = parse_pages(loaded.pages, doc)
        entries.append(
            summarize(
                doc,
                result,
                pdf=pdf_path.relative_to(REPO_ROOT).as_posix(),
                pdf_sha256=sha256_of(pdf_path),
                pages=len(loaded.pages),
            )
        )

    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "documents": entries,
    }
    report["all_clean"] = all(
        not entry.get("error") and entry.get("node_id_unique") and not entry.get("errors")
        for entry in entries
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for entry in entries:
        if entry.get("error"):
            print(f"{entry['doc_id']}: {entry['error']}")
            continue
        print(
            f"{entry['doc_id']}: pages={entry['pages']} nodes={entry['node_count']} "
            f"unique={entry['node_id_unique']} missing={entry['missing_articles']} "
            f"chapter={entry['stats'].get('chapter')} article={entry['stats'].get('article')} "
            f"clause={entry['stats'].get('clause')} point={entry['stats'].get('point')} "
            f"errors={len(entry['errors'])}"
        )
    print(f"report: {args.report.as_posix()}")
    print(f"all_clean={report['all_clean']}")
    return 0 if report["all_clean"] else 1


if __name__ == "__main__":
    sys.exit(main())