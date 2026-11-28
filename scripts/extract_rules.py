"""Sinh `rules/*.yaml` từ text đã parse, mỗi rule kèm câu trích nguyên văn (SPEC §12).

Nguyên tắc: không gõ tay giá trị pháp lý. Mỗi rule phải tìm được câu trích trong node text;
không tìm thấy thì script exit khác 0 và ghi rõ rule nào thiếu, không ghi giá trị mặc định.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from src.common.paths import PROCESSED_DIR, REPO_ROOT

SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+")
RULES_DIR = REPO_ROOT / "rules"


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """Một giá trị pháp lý cần trích: thuộc Điều nào, nhận ra bằng marker nào."""

    key: str
    article: str
    unit: str
    kind: str
    marker: str
    value_pattern: str


@dataclass(frozen=True, slots=True)
class RuleFile:
    filename: str
    description: str
    rules: tuple[RuleSpec, ...]


def sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_SPLIT.split(text) if part.strip()]


def load_nodes() -> list[dict]:
    path = PROCESSED_DIR / "nodes.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def dump(nodes: list[dict], articles: set[str]) -> None:
    """In các câu có số liệu của những Điều cần soát, để viết marker đúng chữ thật."""
    for node in nodes:
        if node.get("article") not in articles:
            continue
        for sentence in sentences(node.get("text") or ""):
            if re.search(r"\d+\s*(%|ngày|giờ)", sentence):
                print(f"{node['node_id']}\t{sentence}")
        lead_in = node.get("lead_in") or ""
        if lead_in and re.search(r"\d+\s*(%|ngày|giờ)", lead_in):
            print(f"{node['node_id']}\tLEAD_IN: {lead_in}")


def extract(nodes: list[dict], spec: RuleSpec, *, doc_id: str) -> dict | None:
    """Tìm câu trích chứa marker và giá trị; trả None nếu không có trong văn bản."""
    for node in nodes:
        if node.get("doc_id") != doc_id or node.get("article") != spec.article:
            continue
        for sentence in sentences(node.get("text") or ""):
            if spec.marker.lower() not in sentence.lower():
                continue
            match = re.search(spec.value_pattern, sentence)
            if not match:
                continue
            return {
                "key": spec.key,
                "value": int(match.group("value")),
                "unit": spec.unit,
                "kind": spec.kind,
                "source_node_id": node["node_id"],
                "evidence": sentence,
            }
    return None


def write_rule_file(
    path: Path, rule_file: RuleFile, extracted: list[dict], doc_id: str, as_of: str
) -> str:
    payload = {
        "doc_id": doc_id,
        "as_of": as_of,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "data/processed/nodes.jsonl",
        "description": rule_file.description,
        "rules": sorted(extracted, key=lambda rule: rule["key"]),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "# Sinh tự động bởi scripts/extract_rules.py — không sửa tay.\n" + yaml.safe_dump(
        payload, allow_unicode=True, sort_keys=False, width=1000
    )
    path.write_text(text, encoding="utf-8")
    return path.relative_to(REPO_ROOT).as_posix()
RULE_FILES: tuple[RuleFile, ...] = (
    RuleFile(
        filename="overtime.yaml",
        description="Tiền lương làm thêm giờ, làm việc ban đêm và giới hạn giờ làm thêm",
        rules=(
            RuleSpec(
                key="ot_weekday",
                article="98",
                unit="%",
                kind="minimum",
                marker="vào ngày thường",
                value_pattern=r"(?P<value>\d+)\s*%",
            ),
            RuleSpec(
                key="ot_weekend",
                article="98",
                unit="%",
                kind="minimum",
                marker="ngày nghỉ hằng tuần",
                value_pattern=r"(?P<value>\d+)\s*%",
            ),
            RuleSpec(
                key="ot_holiday",
                article="98",
                unit="%",
                kind="minimum",
                marker="ngày nghỉ lễ, tết",
                value_pattern=r"(?P<value>\d+)\s*%",
            ),
            RuleSpec(
                key="night_extra",
                article="98",
                unit="%",
                kind="exact",
                marker="làm việc vào ban đêm",
                value_pattern=r"(?P<value>\d+)\s*%",
            ),
            RuleSpec(
                key="night_ot_extra",
                article="98",
                unit="%",
                kind="exact",
                marker="làm thêm giờ vào ban đêm",
                value_pattern=r"trả thêm\s+(?P<value>\d+)\s*%",
            ),
            RuleSpec(
                key="ot_hours_year",
                article="107",
                unit="giờ/năm",
                kind="maximum",
                marker="trừ trường hợp quy định tại khoản 3",
                value_pattern=r"không quá\s+(?P<value>\d+)\s*giờ",
            ),
            RuleSpec(
                key="ot_hours_year_special",
                article="107",
                unit="giờ/năm",
                kind="maximum",
                marker="công việc hoặc trường hợp sau đây",
                value_pattern=r"không quá\s+(?P<value>\d+)\s*giờ",
            ),
            RuleSpec(
                key="ot_hours_month",
                article="107",
                unit="giờ/tháng",
                kind="maximum",
                marker="trong 01 tháng",
                value_pattern=r"không quá\s+(?P<value>\d+)\s*giờ",
            ),
        ),
    ),
    RuleFile(
        filename="leave.yaml",
        description="Nghỉ hằng năm",
        rules=(
            RuleSpec(
                key="annual_leave_base",
                article="113",
                unit="ngày",
                kind="exact",
                marker="điều kiện bình thường",
                value_pattern=r"(?P<value>\d+)\s*ngày làm việc",
            ),
            RuleSpec(
                key="annual_leave_hazardous",
                article="113",
                unit="ngày",
                kind="exact",
                marker="chưa thành niên",
                value_pattern=r"(?P<value>\d+)\s*ngày làm việc",
            ),
            RuleSpec(
                key="annual_leave_special_hazardous",
                article="113",
                unit="ngày",
                kind="exact",
                marker="đặc biệt nặng nhọc",
                value_pattern=r"(?P<value>\d+)\s*ngày làm việc",
            ),
            RuleSpec(
                key="annual_leave_seniority_step",
                article="114",
                unit="ngày/5 năm",
                kind="exact",
                marker="05 năm",
                value_pattern=r"thêm(?:\s+tương\s+ứng)?\s+(?P<value>\d+)\s*ngày",
            ),
        ),
    ),
    RuleFile(
        filename="deduction.yaml",
        description="Khấu trừ tiền lương",
        rules=(
            RuleSpec(
                key="deduction_max_percent",
                article="102",
                unit="%",
                kind="maximum",
                marker="khấu trừ",
                value_pattern=r"không được quá\s+(?P<value>\d+)\s*%",
            ),
        ),
    ),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc-id", default="18-VBHN-VPQH-2026")
    parser.add_argument("--as-of", default="2026-11-27")
    parser.add_argument("--dump", action="append", metavar="ARTICLE")
    args = parser.parse_args(argv)

    nodes = load_nodes()
    if args.dump:
        dump(nodes, set(args.dump))
        return 0

    missing: list[str] = []
    written: list[str] = []
    for rule_file in RULE_FILES:
        extracted: list[dict] = []
        for spec in rule_file.rules:
            rule = extract(nodes, spec, doc_id=args.doc_id)
            if rule is None:
                missing.append(f"{rule_file.filename}:{spec.key}")
                continue
            extracted.append(rule)
        if extracted:
            written.append(
                write_rule_file(
                    RULES_DIR / rule_file.filename,
                    rule_file,
                    extracted,
                    args.doc_id,
                    args.as_of,
                )
            )

    for path in written:
        print(f"wrote {path}")
    for key in missing:
        print(f"MISSING {key}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())