"""Mô hình dữ liệu node (SPEC §5)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.common.ids import Level, parse_node_id

Status = Literal["active", "superseded", "repealed"]


class Node(BaseModel):
    """Một đơn vị văn bản: Chương, Mục, Điều, Khoản, Điểm hoặc bảng."""

    node_id: str
    doc_id: str
    level: Level
    path: list[str] = Field(default_factory=list)
    article: str | None = None
    clause: int | None = None
    point: str | None = None
    text: str = ""
    lead_in: str | None = None
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)
    external_refs: list[str] = Field(default_factory=list)
    has_exception: bool = False
    effective_from: date | None = None
    effective_to: date | None = None
    status: Status = "active"
    version: str | None = None
    table_md: str | None = None
    page_span: tuple[int, int] | None = None
    amend_notes: list[str] = Field(default_factory=list)

    @field_validator("node_id")
    @classmethod
    def _check_node_id(cls, value: str) -> str:
        parse_node_id(value)
        return value

    @field_validator("page_span")
    @classmethod
    def _check_page_span(cls, value: tuple[int, int] | None) -> tuple[int, int] | None:
        if value is None:
            return value
        start, end = value
        if start < 1 or end < start:
            raise ValueError(f"page_span không hợp lệ: {value!r}")
        return value

    @model_validator(mode="after")
    def _check_consistency(self) -> Node:
        parsed = parse_node_id(self.node_id)
        if parsed.doc_id != self.doc_id:
            raise ValueError(f"doc_id không khớp node_id: {self.doc_id!r} vs {parsed.doc_id!r}")
        if parsed.level != self.level:
            raise ValueError(f"level không khớp node_id: {self.level} vs {parsed.level}")
        for name in ("article", "clause", "point"):
            expected = getattr(parsed, name)
            actual = getattr(self, name)
            if expected is not None and actual is not None and expected != actual:
                raise ValueError(f"{name} không khớp node_id: {actual!r} vs {expected!r}")
        return self


def citation_label(node: Node, doc_title: str) -> str:
    """Nhãn trích dẫn hiển thị cho người dùng."""
    parts = [doc_title]
    if node.article:
        parts.append(f"Điều {node.article}")
    if node.clause is not None:
        parts.append(f"Khoản {node.clause}")
    if node.point:
        parts.append(f"Điểm {node.point}")
    return "[" + ", ".join(parts) + "]"