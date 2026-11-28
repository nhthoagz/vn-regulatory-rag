"""Build node set, chunk set, ingest report và fallback map (SPEC §6.8, §7, §12).

Chạy `make build` để đọc PDF đã OCR trong `data/raw` và ghi:

- `data/processed/nodes.jsonl`
- `data/processed/chunks_{leaf,clause,article}.jsonl`
- `data/index/fallback_map.json`
- `data/ingest_report.json`

Không gọi mạng, không tải model. Mọi con số trong tài liệu phải copy từ ingest report này.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, date, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from src.common.config import DocumentMeta, load_documents, load_settings
from src.common.ids import Level
from src.common.paths import INDEX_DIR, PROCESSED_DIR, RAW_DIR, REPO_ROOT
from src.common.schema import Node
from src.ingest.chunker import Tier, build_chunks, chunks_sha256
from src.ingest.loader import LoadResult, load_pages
from src.ingest.parser import parse_pages

TIERS: tuple[Tier, ...] = ("leaf", "clause", "article")
CROSS_CHECK_THRESHOLD = 0.97
MISSING_WARNING = (
    "Văn bản hợp nhất {doc_id} đang thiếu Điều {article} do bản scan mất trang in {pages}. "
    "Phần dưới đây trích từ bản gốc {fallback} và chưa đối chiếu được với văn bản hợp nhất."
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> str:
    """Ghi JSONL theo thứ tự cố định và trả sha256 của nội dung vừa ghi."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
    )
    path.write_text(payload, encoding="utf-8")
    return sha256_bytes(payload.encode("utf-8"))


def write_json(path: Path, payload: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return sha256_bytes(text.encode("utf-8"))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def preamble_sentences(loaded: LoadResult, pages: int = 2) -> list[str]:
    """Câu ở đầu văn bản, nơi chứa tên luật và ngày hiệu lực."""
    lines = [line.text for page in loaded.pages[:pages] for line in page.lines]
    text = " ".join(lines)
    return [part.strip() for part in re.split(r"(?<=[.;:])\s+", text) if part.strip()]


def effective_evidence(loaded: LoadResult, doc: DocumentMeta) -> list[str]:
    """Câu trích nguyên văn nói về ngày hiệu lực của chính `doc.effective_from`.

    Trả rỗng khi `effective_from` là None. Test `evidence ⊂ text` kiểm lại câu này
    trên node/preamble nên không được tự viết lại câu chữ.
    """
    if doc.effective_from is None:
        return []
    value = doc.effective_from
    variants = {
        f"{value.day} tháng {value.month} năm {value.year}",
        f"{value.day:02d} tháng {value.month:02d} năm {value.year}",
    }
    text = " ".join(line.text for page in loaded.pages for line in page.lines)
    sentences = [part.strip() for part in re.split(r"(?<=[.;])\s+", text) if part.strip()]
    found = [
        sentence
        for sentence in sentences
        if "hiệu lực" in sentence.lower() and any(item in sentence for item in variants)
    ]
    return found[:3]


def cross_check(
    nodes_by_doc: dict[str, list[Node]],
    doc_a: str,
    doc_b: str,
    threshold: float = CROSS_CHECK_THRESHOLD,
) -> dict[str, Any]:
    """So khớp text Điều giữa hai văn bản; lệch dưới ngưỡng là chỗ cần người soát (SPEC §6.8)."""
    text_a: dict[str | None, str] = {}
    text_b: dict[str | None, str] = {}
    for node in nodes_by_doc[doc_a]:
        if node.level == Level.article:
            text_a[node.article] = node.text
    for node in nodes_by_doc[doc_b]:
        if node.level == Level.article:
            text_b[node.article] = node.text
    common = sorted(set(text_a) & set(text_b), key=lambda value: (len(value), value))
    below: list[dict[str, Any]] = []
    for article in common:
        matcher = SequenceMatcher(None, text_a[article], text_b[article])
        if matcher.quick_ratio() < threshold:
            below.append({"article": article, "ratio": round(matcher.ratio(), 4)})
            continue
        ratio = matcher.ratio()
        if ratio < threshold:
            below.append({"article": article, "ratio": round(ratio, 4)})
    return {
        "doc_a": doc_a,
        "doc_b": doc_b,
        "compared": len(common),
        "threshold": threshold,
        "below_threshold": below,
        "only_in_a": sorted(set(text_a) - set(text_b)),
        "only_in_b": sorted(set(text_b) - set(text_a)),
    }


def build_fallback_map(entries: list[dict[str, Any]], nodes_by_doc: dict[str, list[Node]]) -> dict:
    """Ánh xạ Điều bị thiếu ở văn bản mặc định sang văn bản còn lại, kèm câu cảnh báo."""
    mapping: dict[str, dict[str, Any]] = {}
    for entry in entries:
        missing = entry.get("missing_articles") or []
        if not missing:
            continue
        candidates = [
            other
            for other in entries
            if other["doc_id"] != entry["doc_id"] and other.get("node_count")
        ]
        if not candidates:
            continue
        fallback = candidates[0]
        available = {
            node.article for node in nodes_by_doc[fallback["doc_id"]] if node.level == Level.article
        }
        printed = [
            anomaly["printed_numbers"]
            for anomaly in entry.get("scan_page_anomalies", [])
            if anomaly["kind"] == "missing_printed_pages"
        ]
        page_hint = "; ".join(f"{first}–{second}" for first, second in printed) or "không rõ"
        for article in missing:
            if str(article) not in available:
                continue
            mapping.setdefault(entry["doc_id"], {})[str(article)] = {
                "fallback_doc_id": fallback["doc_id"],
                "reason": "scan_pages_missing",
                "warning": MISSING_WARNING.format(
                    doc_id=entry["doc_id"],
                    article=article,
                    pages=page_hint,
                    fallback=fallback["doc_id"],
                ),
            }
    return mapping


def build(only: list[str] | None = None, as_of: date | None = None) -> dict[str, Any]:
    """Đọc PDF, parse, dựng node/chunk và trả về ingest report (không ghi file)."""
    settings = load_settings()
    documents = load_documents()
    if only:
        wanted = set(only)
        documents = [doc for doc in documents if doc.doc_id in wanted]
        if not documents:
            raise SystemExit(f"không có doc_id nào khớp {only}")

    as_of_date = as_of or settings.docs.as_of or date.today()
    nodes_by_doc: dict[str, list[Node]] = {}
    chunks_by_tier: dict[Tier, list[dict[str, Any]]] = {tier: [] for tier in TIERS}
    chunk_shas: dict[str, dict[str, str]] = {tier: {} for tier in TIERS}
    entries: list[dict[str, Any]] = []

    for doc in documents:
        pdf_path = RAW_DIR / f"{Path(doc.file).stem}-ocr.pdf"
        if not pdf_path.is_file():
            entries.append({"doc_id": doc.doc_id, "error": f"thiếu {pdf_path.name}"})
            continue

        loaded = load_pages(pdf_path)
        parsed = parse_pages(loaded.pages, doc)
        nodes = [
            node.model_copy(update={"status": doc.status, "effective_from": doc.effective_from})
            for node in parsed.nodes
        ]
        nodes.sort(key=lambda node: node.node_id)
        nodes_by_doc[doc.doc_id] = nodes

        title = doc.title or doc.doc_id
        for tier in TIERS:
            chunks = build_chunks(nodes, title, tier=tier)
            chunks_by_tier[tier].extend(chunk.as_dict() for chunk in chunks)
            chunk_shas[tier][doc.doc_id] = chunks_sha256(chunks)

        page_texts = [_norm(" ".join(line.text for line in page.lines)) for page in loaded.pages]
        marker = _norm(doc.identity_marker or "")
        identity_pages = [
            index + 1 for index, text in enumerate(page_texts) if marker and marker in text
        ]
        expected = doc.expected_counts or {}
        actual = {key: parsed.stats.get(key, 0) for key in expected}
        missing = list(parsed.missing_articles)
        counts_ok = all(
            actual[key] == expected[key]
            or (key == "article" and actual[key] + len(missing) == expected[key])
            for key in expected
        )
        node_ids = [node.node_id for node in nodes]
        errors = [
            {"kind": issue.kind, "page": issue.page, "message": issue.message}
            for issue in parsed.issues
            if issue.severity == "error"
        ]
        entries.append(
            {
                "doc_id": doc.doc_id,
                "role": doc.role,
                "status": doc.status,
                "title": doc.title,
                "effective_from": doc.effective_from.isoformat() if doc.effective_from else None,
                "effective_kind": doc.effective_kind,
                "effective_evidence": effective_evidence(loaded, doc),
                "identity_marker": doc.identity_marker,
                "identity_pages": identity_pages,
                "pdf": pdf_path.relative_to(REPO_ROOT).as_posix(),
                "pdf_sha256": sha256_file(pdf_path),
                "pages": len(loaded.pages),
                "line_count": loaded.lines_total,
                "dropped_running_heads": loaded.lines_dropped,
                "stats": dict(sorted(parsed.stats.items())),
                "expected_counts": expected,
                "counts_ok": counts_ok,
                "missing_articles": missing,
                "scan_page_anomalies": [
                    {
                        "kind": anomaly.kind,
                        "pdf_pages": list(anomaly.pdf_pages),
                        "printed_numbers": list(anomaly.printed_numbers),
                        "detail": anomaly.detail,
                    }
                    for anomaly in loaded.anomalies
                ],
                "node_count": len(nodes),
                "node_id_unique": len(node_ids) == len(set(node_ids)),
                "chunk_counts": {
                    tier: len(
                        [chunk for chunk in chunks_by_tier[tier] if chunk["doc_id"] == doc.doc_id]
                    )
                    for tier in TIERS
                },
                "errors": errors,
            }
        )

    doc_ids = [entry["doc_id"] for entry in entries if "error" not in entry]
    cross = None
    if len(doc_ids) == 2:
        cross = cross_check(nodes_by_doc, doc_ids[0], doc_ids[1])

    all_nodes = [node for doc_id in doc_ids for node in nodes_by_doc[doc_id]]
    all_nodes.sort(key=lambda node: (node.doc_id, node.node_id))

    return {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "as_of": as_of_date.isoformat(),
        "documents": entries,
        "cross_check": cross,
        "fallback_map": build_fallback_map(entries, nodes_by_doc),
        "node_records": [node.model_dump(mode="json") for node in all_nodes],
        "chunks": chunks_by_tier,
        "chunk_shas": chunk_shas,
    }


def write_artifacts(report: dict[str, Any], report_path: Path) -> dict[str, Any]:
    """Ghi node/chunk/fallback/ingest report và trả về payload report kèm sha256."""
    node_sha = write_jsonl(PROCESSED_DIR / "nodes.jsonl", report["node_records"])
    chunk_files: dict[str, dict[str, Any]] = {}
    for tier in TIERS:
        records = sorted(report["chunks"][tier], key=lambda record: record["chunk_id"])
        path = PROCESSED_DIR / f"chunks_{tier}.jsonl"
        chunk_files[tier] = {
            "path": path.relative_to(REPO_ROOT).as_posix(),
            "records": len(records),
            "sha256": write_jsonl(path, records),
            "per_doc_sha256": report["chunk_shas"][tier],
        }
    fallback_sha = write_json(INDEX_DIR / "fallback_map.json", report["fallback_map"])
    payload = {
        "generated_at": report["generated_at"],
        "as_of": report["as_of"],
        "documents": report["documents"],
        "cross_check": report["cross_check"],
        "fallback_map": report["fallback_map"],
        "files": {
            "nodes": {
                "path": (PROCESSED_DIR / "nodes.jsonl").relative_to(REPO_ROOT).as_posix(),
                "records": len(report["node_records"]),
                "sha256": node_sha,
            },
            "chunks": chunk_files,
            "fallback_map": {
                "path": (INDEX_DIR / "fallback_map.json").relative_to(REPO_ROOT).as_posix(),
                "sha256": fallback_sha,
            },
        },
    }
    payload["status"] = (
        "ok"
        if all(
            "error" not in entry and entry["node_id_unique"] and not entry["errors"]
            for entry in payload["documents"]
        )
        else "error"
    )
    write_json(report_path, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", metavar="DOC_ID")
    parser.add_argument("--as-of", dest="as_of", type=date.fromisoformat, default=None)
    parser.add_argument("--report", type=Path, default=REPO_ROOT / "data" / "ingest_report.json")
    args = parser.parse_args(argv)

    report = build(only=args.only, as_of=args.as_of)
    payload = write_artifacts(report, args.report)

    for entry in payload["documents"]:
        if "error" in entry:
            print(f"{entry['doc_id']}: {entry['error']}")
            continue
        print(
            f"{entry['doc_id']}: pages={entry['pages']} nodes={entry['node_count']} "
            f"article={entry['stats'].get('article')} missing={entry['missing_articles']} "
            f"chunks={entry['chunk_counts']} identity_pages={entry['identity_pages']}"
        )
    print(f"nodes_sha={payload['files']['nodes']['sha256']}")
    print(f"report: {args.report.relative_to(REPO_ROOT).as_posix()} status={payload['status']}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())