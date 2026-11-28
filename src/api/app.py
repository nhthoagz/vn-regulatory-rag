"""API hỏi đáp có trích dẫn (SPEC §10). Một pipeline, nạp một lần khi khởi động."""

from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.common.config import load_settings
from src.common.paths import INDEX_DIR, PROCESSED_DIR
from src.core import tools
from src.core.pipeline import Pipeline

app = FastAPI(title="vn-regulatory-rag", version="0.1.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)
    mode: str = Field(default="bm25", pattern="^(bm25|dense|linear|rrf)$")


class AskResponse(BaseModel):
    answer: str
    citations: list[str]
    node_ids: list[str]
    warnings: list[str]
    refused: bool
    intent: str
    violations: list[str]


class OvertimeRequest(BaseModel):
    hourly_wage: Decimal = Field(gt=0)
    hours: Decimal = Field(gt=0, le=400)
    kind: str = Field(default="weekday", pattern="^(weekday|weekend|holiday|night)$")


class LeaveRequest(BaseModel):
    years_of_service: int = Field(ge=0, le=60)
    base_days: int = Field(default=0, ge=0, le=20)


@lru_cache(maxsize=4)
def get_pipeline(mode: str = "bm25") -> Pipeline:
    """Nạp pipeline theo mode; mode khác bm25 cần numpy + model đã tải."""
    settings = load_settings()
    return Pipeline(
        chunks_path=PROCESSED_DIR / "chunks_leaf.jsonl",
        nodes_path=PROCESSED_DIR / "nodes.jsonl",
        fallback_path=INDEX_DIR / "fallback_map.json",
        default_doc_id=settings.docs.default_doc_id,
        mode=mode,
        dense_model=os.environ.get("DENSE_MODEL", "bge-m3"),
    )


@app.get("/health")
def health() -> dict:
    pipeline = get_pipeline()
    return {
        "status": "ok",
        "chunks": len(pipeline.chunks),
        "nodes": len(pipeline.nodes),
        "rules": len(pipeline.rules),
    }


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    try:
        pipeline = get_pipeline(request.mode)
    except (ImportError, ValueError) as error:
        raise HTTPException(
            status_code=503, detail=f"mode {request.mode} chưa sẵn sàng: {error}"
        ) from error
    result = pipeline.ask(request.question, top_k=request.top_k)
    return AskResponse(
        answer=result.answer,
        citations=result.citations,
        node_ids=result.node_ids,
        warnings=result.warnings,
        refused=result.refused,
        intent=result.intent,
        violations=result.violations,
    )


@app.post("/calc/overtime")
def calc_overtime(request: OvertimeRequest) -> dict:
    rules = tools.load_rules()
    try:
        result = tools.overtime(request.hourly_wage, request.hours, request.kind, rules)
    except tools.CalcError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    rule = rules[result.rule_key]
    amount = result.amount
    amount_text = str(int(amount)) if amount == amount.to_integral_value() else str(amount)
    return {
        "amount": amount_text,
        "rate_percent": result.rate_percent,
        "source_node_id": rule["source_node_id"],
        "evidence": rule["evidence"],
    }


@app.post("/calc/leave")
def calc_leave(request: LeaveRequest) -> dict:
    rules = tools.load_rules()
    base = request.base_days or int(rules["annual_leave_base"]["value"])
    try:
        days, node_id = tools.annual_leave_days(base, request.years_of_service, rules)
    except tools.CalcError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"days": days, "base_days": base, "source_node_id": node_id}