from __future__ import annotations

import json

import pytest
import yaml

from src.common.paths import PROCESSED_DIR, REPO_ROOT

RULE_FILES = sorted((REPO_ROOT / "rules").glob("*.yaml"))


@pytest.mark.realdata
def test_every_rule_has_verbatim_evidence_from_a_node() -> None:
    nodes: dict[str, str] = {}
    for line in (PROCESSED_DIR / "nodes.jsonl").read_text(encoding="utf-8").splitlines():
        node = json.loads(line)
        nodes[node["node_id"]] = node["text"]

    rules = []
    for path in RULE_FILES:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert payload["doc_id"], path.name
        rules.extend(payload["rules"])

    assert rules, "chưa có rule nào; chạy `python -m scripts.extract_rules`"
    for rule in rules:
        assert rule["source_node_id"] in nodes, rule["key"]
        assert rule["evidence"] in nodes[rule["source_node_id"]], rule["key"]
        assert str(rule["value"]) in rule["evidence"], rule["key"]
        assert rule["kind"] in {"minimum", "maximum", "exact"}, rule["key"]
        assert rule["unit"], rule["key"]


@pytest.mark.realdata
def test_core_labour_values_match_the_law_text() -> None:
    """Giá trị then chốt phải đúng như câu trích, không phải số gõ tay."""
    rules: dict[str, int] = {}
    for path in RULE_FILES:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        for rule in payload["rules"]:
            rules[rule["key"]] = rule["value"]

    assert rules["ot_weekday"] == 150
    assert rules["ot_weekend"] == 200
    assert rules["ot_holiday"] == 300
    assert rules["night_extra"] == 30
    assert rules["night_ot_extra"] == 20
    assert rules["ot_hours_year"] == 200
    assert rules["ot_hours_year_special"] == 300
    assert rules["annual_leave_base"] == 12
    assert rules["annual_leave_hazardous"] == 14
    assert rules["annual_leave_special_hazardous"] == 16
    assert rules["deduction_max_percent"] == 30