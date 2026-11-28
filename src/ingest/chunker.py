"""Tạo chunk truy xuất từ node đã parse (SPEC §7).

Index ở mức lá: Điểm > Khoản > Điều (bảng cũng là lá). `text` của chunk = header trích dẫn
(theo `header_mode`) + `lead_in` của node + `text` của node. Ba tầng `leaf|clause|article`
được build cùng nhau để làm ablation như SPEC §11 yêu cầu.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from src.common.ids import Level
from src.common.schema import Node, citation_label

HeaderMode = Literal["none", "true", "placebo"]
Tier = Literal["leaf", "clause", "article"]

LEAF_LEVELS = (Level.point, Level.clause, Level.article, Level.table)


@dataclass(frozen=True, slots=True)
class Chunk:
    """Một đơn vị được đánh index, giữ đủ metadata để render trích dẫn."""

    chunk_id: str
    doc_id: str
    node_id: str
    level: str
    article: str | None
    clause: int | None
    point: str | None
    page_span: tuple[int, int] | None
    text: str
    citation: str
    has_exception: bool
    refs: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "node_id": self.node_id,
            "level": self.level,
            "article": self.article,
            "clause": self.clause,
            "point": self.point,
            "page_span": list(self.page_span) if self.page_span else None,
            "text": self.text,
            "citation": self.citation,
            "has_exception": self.has_exception,
            "refs": list(self.refs),
        }


def select_nodes(nodes: list[Node], tier: Tier) -> list[Node]:
    """Chọn node theo tầng index; `leaf` bỏ node còn con để không index hai lần."""
    if tier == "leaf":
        return [node for node in nodes if not node.children and node.level in LEAF_LEVELS]
    if tier == "clause":
        return [
            node
            for node in nodes
            if node.level == Level.clause
            or (node.level == Level.article and not node.children)
        ]
    return [node for node in nodes if node.level == Level.article]


def descendant_text(node: Node, nodes: list[Node]) -> str:
    """Text của toàn bộ node con/cháu, dùng khi index ở tầng khoản hoặc điều."""
    prefix = f"{node.node_id}."
    return "\n".join(
        other.text for other in nodes if other.node_id.startswith(prefix) and other.text
    )


def placebo_label(node: Node, nodes: list[Node], doc_title: str) -> str:
    """Nhãn trích dẫn của một node khác, chọn tất định theo node_id (SPEC §7 ablation)."""
    pool = sorted(
        (
            other
            for other in nodes
            if other.node_id != node.node_id and other.article is not None
        ),
        key=lambda other: other.node_id,
    )
    if not pool:
        return citation_label(node, doc_title)
    index = int(hashlib.sha256(node.node_id.encode("utf-8")).hexdigest()[:8], 16) % len(pool)
    return citation_label(pool[index], doc_title)


def make_chunk(
    node: Node,
    doc_title: str,
    *,
    header_mode: HeaderMode = "true",
    nodes: list[Node] | None = None,
    include_children: bool = False,
) -> Chunk:
    """Dựng chunk cho một node; `header_mode=placebo` cần `nodes` để chọn nhãn khác."""
    citation = citation_label(node, doc_title)
    header = ""
    if header_mode == "true":
        header = citation
    elif header_mode == "placebo":
        header = placebo_label(node, nodes or [], doc_title)

    children = descendant_text(node, nodes) if include_children and nodes else ""
    parts = [header, node.lead_in or "", node.table_md or "", node.text, children]
    text = "\n".join(part for part in parts if part).strip()
    return Chunk(
        chunk_id=node.node_id,
        doc_id=node.doc_id,
        node_id=node.node_id,
        level=str(node.level),
        article=node.article,
        clause=node.clause,
        point=node.point,
        page_span=node.page_span,
        text=text,
        citation=citation,
        has_exception=node.has_exception,
        refs=tuple(node.refs),
    )


def build_chunks(
    nodes: list[Node],
    doc_title: str,
    *,
    tier: Tier = "leaf",
    header_mode: HeaderMode = "true",
) -> list[Chunk]:
    """Dựng toàn bộ chunk của một văn bản, sort theo `chunk_id` để build tất định."""
    selected = select_nodes(nodes, tier)
    chunks = [
        make_chunk(
            node,
            doc_title,
            header_mode=header_mode,
            nodes=nodes,
            include_children=tier != "leaf",
        )
        for node in selected
    ]
    return sorted(chunks, key=lambda chunk: chunk.chunk_id)


def chunks_sha256(chunks: list[Chunk]) -> str:
    """sha256 của tập chunk (dùng làm cache key và ghi vào report)."""
    digest = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda item: item.chunk_id):
        payload = json.dumps(chunk.as_dict(), ensure_ascii=False, sort_keys=True)
        digest.update(payload.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()