"""Công cụ tính toán tất định cho câu hỏi định lượng (SPEC §9).

Giá trị pháp lý (150%, 200 giờ, 12 ngày...) đọc từ `rules/*.yaml`, không viết lại trong code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from src.common.paths import REPO_ROOT

MONEY_UNITS = {
    "triệu": Decimal(1_000_000),
    "tr": Decimal(1_000_000),
    "trieu": Decimal(1_000_000),
    "nghìn": Decimal(1_000),
    "ngan": Decimal(1_000),
}
MONEY_RE = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)\s*(?P<unit>triệu|trieu|tr|nghìn|ngan)?", re.I)
OT_KINDS = {
    "weekday": "ot_weekday",
    "weekend": "ot_weekend",
    "holiday": "ot_holiday",
    "night": "night_extra",
}


class CalcError(ValueError):
    """Thiếu dữ liệu hoặc dữ liệu không hợp lệ để tính."""


def load_rules(paths: list[Path] | None = None) -> dict[str, dict]:
    """Nạp toàn bộ rule theo `key`; giữ `evidence` để render trích dẫn."""
    rules: dict[str, dict] = {}
    files = paths or sorted((REPO_ROOT / "rules").glob("*.yaml"))
    for path in files:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rule in payload["rules"]:
            rules[rule["key"]] = rule
    return rules


def parse_money(text: str) -> Decimal:
    """Đọc số tiền: '5 triệu', '5tr', '5.000.000', '5,5 triệu'."""
    cleaned = text.strip().lower()
    match = MONEY_RE.search(cleaned)
    if not match:
        raise CalcError(f"không đọc được số tiền trong {text!r}")
    number = match.group("num")
    unit = match.group("unit")
    thousands = re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", number)

    if unit and not thousands:
        # "5,5 triệu" / "5.5 triệu": dấu phân cách là dấu thập phân.
        raw = number.replace(",", ".")
    elif thousands:
        raw = re.sub(r"[.,]", "", number)
    else:
        raw = number.replace(",", ".")
    try:
        value = Decimal(raw)
    except InvalidOperation as error:
        raise CalcError(f"số tiền không hợp lệ: {text!r}") from error
    if unit:
        value *= MONEY_UNITS[unit.lower()]
    return value


def parse_hours(text: str) -> Decimal:
    match = re.search(r"(?P<num>\d+(?:[.,]\d+)?)", text)
    if not match:
        raise CalcError(f"không đọc được số giờ trong {text!r}")
    return Decimal(match.group("num").replace(",", "."))


@dataclass(frozen=True, slots=True)
class OvertimeResult:
    amount: Decimal
    rate_percent: int
    hours: Decimal
    hourly_wage: Decimal
    rule_key: str


def overtime(
    hourly_wage: Decimal, hours: Decimal, kind: str, rules: dict[str, dict]
) -> OvertimeResult:
    """Tính tiền làm thêm giờ cho một loại ngày; không hỗ trợ chồng ca đêm + làm thêm."""
    if kind not in OT_KINDS:
        raise CalcError(f"loại ngày không hỗ trợ: {kind}")
    rule = rules.get(OT_KINDS[kind])
    if rule is None:
        raise CalcError(f"thiếu rule {OT_KINDS[kind]} trong rules/*.yaml")
    rate = int(rule["value"])
    multiplier = Decimal(rate) / Decimal(100)
    return OvertimeResult(
        amount=hourly_wage * multiplier * hours,
        rate_percent=rate,
        hours=hours,
        hourly_wage=hourly_wage,
        rule_key=rule["key"],
    )


def annual_leave_days(
    base_days: int, years_of_service: int, rules: dict[str, dict]
) -> tuple[int, str]:
    """Điều 114: cứ đủ 5 năm làm việc thì tăng thêm 1 ngày (rule `annual_leave_seniority_step`)."""
    rule = rules.get("annual_leave_seniority_step")
    if rule is None:
        raise CalcError("thiếu rule annual_leave_seniority_step")
    step_days = int(rule["value"])
    if years_of_service < 0:
        raise CalcError("số năm làm việc không hợp lệ")
    return base_days + (years_of_service // 5) * step_days, rule["source_node_id"]