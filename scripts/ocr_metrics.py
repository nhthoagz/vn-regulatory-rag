"""Structural OCR metrics: how much of the legal structure survived OCR.

Counts are objective proxies for character accuracy: a clause marker that OCR
turned into a comma, or a Chapter numeral that came out wrong, is structure lost.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

CHAPTER_RE = re.compile(r"^Chương\s+([IVXLC]+)\b", re.MULTILINE)
ARTICLE_RE = re.compile(r"^Điều\s+(\d+[a-zđ]?)\.", re.MULTILINE)
ARTICLE_ANY_RE = re.compile(r"^\s*Điều\s+(\d+[a-zđ]?)", re.MULTILINE)
CLAUSE_DOT_RE = re.compile(r"^\d+\.\s", re.MULTILINE)
CLAUSE_COMMA_RE = re.compile(r"^\d+,\s", re.MULTILINE)
POINT_RE = re.compile(r"^[abcdđeghiklmnopqrstuvxy]\)\s", re.MULTILINE)


def metrics(text: str) -> dict[str, int]:
    return {
        "chapters": len(CHAPTER_RE.findall(text)),
        "articles_with_dot": len(ARTICLE_RE.findall(text)),
        "articles_any": len(ARTICLE_ANY_RE.findall(text)),
        "clause_markers_dot": len(CLAUSE_DOT_RE.findall(text)),
        "clause_markers_comma": len(CLAUSE_COMMA_RE.findall(text)),
        "point_markers": len(POINT_RE.findall(text)),
        "chars": len(text),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    for path in args.paths:
        result = metrics(path.read_text(encoding="utf-8"))
        joined = " ".join(f"{key}={value}" for key, value in result.items())
        print(f"{path.name}: {joined}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())