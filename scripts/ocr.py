"""OCR the source scans and report per-page text quality.

Quality gate and document identity check follow SPEC sections 2 and 6.1.
Run through `make ocr`, a long job, so launch it with nohup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
REVIEW_DIR = RAW_DIR / "review"
CONFIG_PATH = REPO_ROOT / "config" / "docs.yaml"
REPORT_PATH = REPO_ROOT / "results" / "ocr_report.json"

MIN_CHARS = 50
MIN_OK_RATIO = 0.95


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tool_version(args: list[str]) -> str:
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    text = (result.stdout or result.stderr).strip().splitlines()
    return text[0].strip() if text else "unknown"


def load_documents() -> list[dict[str, Any]]:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    documents = data.get("documents") or []
    if not documents:
        raise SystemExit(f"no documents configured in {CONFIG_PATH}")
    return documents


def extract_pages(pdf: Path) -> list[str]:
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"pdftotext failed on {pdf}: {result.stderr.strip()}")
    pages = result.stdout.split("\f")
    while pages and not pages[-1].strip():
        pages.pop()
    return pages


def quality(pages: list[str]) -> tuple[int, float]:
    ok = sum(1 for page in pages if len(page.strip()) >= MIN_CHARS)
    ratio = ok / len(pages) if pages else 0.0
    return ok, round(ratio, 4)

def run_ocrmypdf(
    src: Path,
    dst: Path,
    sidecar: Path,
    jobs: int,
    oversample: int | None,
    tessdata_dir: Path | None = None,
) -> dict[str, Any]:
    cmd = [
        "ocrmypdf",
        "-l",
        "vie",
        "--rotate-pages",
        "--deskew",
        "--clean",
        "--invalidate-digital-signatures",
        "--jobs",
        str(jobs),
        "--sidecar",
        str(sidecar),
    ]
    if oversample:
        cmd += ["--oversample", str(oversample), "--force-ocr"]
    cmd += [str(src), str(dst)]

    env = dict(os.environ)
    if tessdata_dir:
        # ocrmypdf has no --tessdata-dir flag; it forwards TESSDATA_PREFIX to tesseract.
        env["TESSDATA_PREFIX"] = str(tessdata_dir)

    started = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    return {
        "command": " ".join(cmd),
        "tessdata_prefix": str(tessdata_dir) if tessdata_dir else None,
        "exit_code": result.returncode,
        "seconds": round(time.monotonic() - started, 1),
        "stderr_tail": result.stderr.strip().splitlines()[-8:],
    }


def write_review(stem: str, pages: list[str]) -> Path:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    path = REVIEW_DIR / f"{stem}.md"
    lines = [
        f"# OCR review — `{stem}`",
        "",
        f"- Số trang: {len(pages)}",
        f"- Ngưỡng chất lượng: >= {MIN_CHARS} ký tự/trang",
        "",
        "Đối chiếu từng trang với `*-ocr.pdf` (file gốc đã có text layer để bôi đen / Ctrl+F).",
        "",
    ]
    for number, text in enumerate(pages, start=1):
        lines.append(f"=== Trang {number} ===")
        lines.append("")
        lines.append(text.strip())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def process(
    doc: dict[str, Any],
    jobs: int,
    force: bool,
    suffix: str,
    tessdata_dir: Path | None,
) -> dict[str, Any]:
    src = RAW_DIR / doc["file"]
    stem = src.stem
    dst = RAW_DIR / f"{stem}{suffix}.pdf"
    sidecar = RAW_DIR / f"{stem}{suffix}.txt"
    if not src.is_file():
        return {"doc_id": doc["doc_id"], "error": f"missing source: {src}"}

    entry: dict[str, Any] = {
        "doc_id": doc["doc_id"],
        "role": doc.get("role"),
        "source": src.relative_to(REPO_ROOT).as_posix(),
        "source_sha256": sha256_of(src),
        "source_bytes": src.stat().st_size,
        "output": dst.relative_to(REPO_ROOT).as_posix(),
        "sidecar": sidecar.relative_to(REPO_ROOT).as_posix(),
        "identity_marker": doc.get("identity_marker"),
        "skipped": False,
        "retried": False,
    }

    if dst.is_file() and not force:
        entry["skipped"] = True
    else:
        entry["run"] = run_ocrmypdf(src, dst, sidecar, jobs, None, tessdata_dir)
        if entry["run"]["exit_code"] != 0:
            entry["error"] = "ocrmypdf failed"
            return entry
    entry["output_sha256"] = sha256_of(dst)

    pages = extract_pages(dst)
    ok, ratio = quality(pages)
    entry.update({"pages": len(pages), "pages_ok": ok, "ok_ratio": ratio})

    if ratio < MIN_OK_RATIO and not entry["skipped"]:
        entry["retried"] = True
        entry["retry_run"] = run_ocrmypdf(src, dst, sidecar, jobs, 300, tessdata_dir)
        entry["output_sha256"] = sha256_of(dst)
        pages = extract_pages(dst)
        ok, ratio = quality(pages)
        entry.update({"pages": len(pages), "pages_ok": ok, "ok_ratio": ratio})

    marker = (doc.get("identity_marker") or "").strip()
    identity_page = None
    if marker:
        for number, text in enumerate(pages, start=1):
            if marker in text:
                identity_page = number
                break
    entry["identity_page"] = identity_page
    entry["review"] = write_review(stem, pages).relative_to(REPO_ROOT).as_posix()
    entry["pass"] = bool(marker) and identity_page is not None and ratio >= MIN_OK_RATIO
    return entry

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=4, help="ocrmypdf worker count")
    parser.add_argument("--force", action="store_true", help="re-run even if the output exists")
    parser.add_argument("--only", action="append", metavar="DOC_ID", help="restrict to a doc_id")
    parser.add_argument("--suffix", default="-ocr", help="output suffix, e.g. -ocr or -best")
    parser.add_argument("--tessdata-dir", type=Path, default=None, help="custom tessdata directory")
    parser.add_argument("--report", type=Path, default=REPORT_PATH, help="report JSON path")
    args = parser.parse_args(argv)

    documents = load_documents()
    if args.only:
        wanted = set(args.only)
        documents = [doc for doc in documents if doc["doc_id"] in wanted]
        if not documents:
            return 2

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    started = time.monotonic()
    entries = [
        process(doc, args.jobs, args.force, args.suffix, args.tessdata_dir) for doc in documents
    ]
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": {
            "ocrmypdf": tool_version(["ocrmypdf", "--version"]),
            "tesseract": tool_version(["tesseract", "--version"]),
            "pdftotext": tool_version(["pdftotext", "-v"]),
        },
        "settings": {
            "lang": "vie",
            "jobs": args.jobs,
            "suffix": args.suffix,
            "tessdata_dir": str(args.tessdata_dir) if args.tessdata_dir else None,
            "min_chars": MIN_CHARS,
            "min_ok_ratio": MIN_OK_RATIO,
            "invalidate_digital_signatures": True,
        },
        "total_seconds": round(time.monotonic() - started, 1),
        "documents": entries,
    }
    report["all_pass"] = all(bool(entry.get("pass")) for entry in entries)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for entry in entries:
        print(
            f"{entry.get('doc_id')}: pages={entry.get('pages')} "
            f"ok={entry.get('pages_ok')} ratio={entry.get('ok_ratio')} "
            f"identity_page={entry.get('identity_page')} pass={entry.get('pass')} "
            f"skipped={entry.get('skipped')} retried={entry.get('retried')} "
            f"error={entry.get('error')}"
        )
    print(f"report: {args.report.as_posix()}")
    print(f"all_pass={report['all_pass']} total_seconds={report['total_seconds']}")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())