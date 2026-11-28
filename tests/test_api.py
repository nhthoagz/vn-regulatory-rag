from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app

client = TestClient(app)


def test_health_reports_loaded_index() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["chunks"] > 0
    assert payload["rules"] >= 13


@pytest.mark.realdata
def test_ask_returns_citation_inside_allowed_nodes() -> None:
    response = client.post(
        "/ask", json={"question": "Điều 98 quy định mức lương làm thêm giờ thế nào?"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert not payload["violations"]
    assert payload["node_ids"]
    assert payload["citations"]
    assert not payload["refused"]


@pytest.mark.realdata
def test_ask_refuses_out_of_scope_question() -> None:
    response = client.post(
        "/ask", json={"question": "Thuế thu nhập doanh nghiệp của công ty Hàn Quốc là bao nhiêu?"}
    )
    payload = response.json()
    assert payload["refused"] is True


@pytest.mark.realdata
def test_ask_warns_when_article_missing_from_consolidated_document() -> None:
    response = client.post("/ask", json={"question": "Điều 76 quy định gì?"})
    payload = response.json()
    assert payload["warnings"]
    assert payload["node_ids"]
    assert "thiếu Điều 76" in payload["warnings"][0]


def test_calc_overtime_uses_rule_from_yaml() -> None:
    response = client.post(
        "/calc/overtime", json={"hourly_wage": "50000", "hours": "4", "kind": "weekday"}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["amount"] == "300000"
    assert payload["rate_percent"] == 150
    assert payload["source_node_id"].endswith("D98.K1.a")


def test_calc_leave_adds_seniority_days() -> None:
    response = client.post("/calc/leave", json={"years_of_service": 11, "base_days": 12})
    assert response.status_code == 200
    assert response.json()["days"] == 14


def test_calc_rejects_invalid_kind() -> None:
    response = client.post(
        "/calc/overtime", json={"hourly_wage": "50000", "hours": "2", "kind": "sunday"}
    )
    assert response.status_code == 422