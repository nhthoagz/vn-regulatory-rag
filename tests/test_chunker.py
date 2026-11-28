from __future__ import annotations

from src.common.ids import Level
from src.common.schema import Node
from src.ingest.chunker import build_chunks, chunks_sha256, select_nodes


def make_node(node_id: str, level: Level, text: str, **kwargs: object) -> Node:
    doc_id = node_id.split(":")[0]
    return Node(node_id=node_id, doc_id=doc_id, level=level, text=text, **kwargs)


def sample_nodes() -> list[Node]:
    return [
        make_node(
            "T:D5",
            Level.article,
            "Điều 5. Người lao động có quyền.",
            article="5",
            children=["T:D5.K1"],
        ),
        make_node(
            "T:D5.K1",
            Level.clause,
            "1. Làm việc.",
            parent_id="T:D5",
            article="5",
            clause=1,
            children=["T:D5.K1.a"],
        ),
        make_node(
            "T:D5.K1.a",
            Level.point,
            "a) Được trả lương.",
            parent_id="T:D5.K1",
            lead_in="1. Làm việc.",
            article="5",
            clause=1,
            point="a",
        ),
        make_node("T:D6", Level.article, "Điều 6. Nghĩa vụ.", article="6"),
    ]


def test_select_leaf_skips_nodes_with_children() -> None:
    nodes = sample_nodes()
    ids = [node.node_id for node in select_nodes(nodes, "leaf")]
    assert ids == ["T:D5.K1.a", "T:D6"]


def test_select_clause_and_article_tiers() -> None:
    nodes = sample_nodes()
    assert [node.node_id for node in select_nodes(nodes, "clause")] == ["T:D5.K1", "T:D6"]
    assert [node.node_id for node in select_nodes(nodes, "article")] == ["T:D5", "T:D6"]


def test_chunk_text_includes_header_and_lead_in() -> None:
    nodes = sample_nodes()
    chunks = {chunk.chunk_id: chunk for chunk in build_chunks(nodes, "Bộ luật Test", tier="leaf")}
    point = chunks["T:D5.K1.a"]
    assert point.text.splitlines()[0] == "[Bộ luật Test, Điều 5, Khoản 1, Điểm a]"
    assert "1. Làm việc." in point.text
    assert "a) Được trả lương." in point.text
    assert point.level == "point"


def test_header_mode_none_drops_header() -> None:
    nodes = sample_nodes()
    chunks = build_chunks(nodes, "Bộ luật Test", tier="leaf", header_mode="none")
    assert all(not chunk.text.startswith("[") for chunk in chunks)


def test_header_mode_placebo_uses_other_article_label() -> None:
    nodes = sample_nodes()
    chunks = build_chunks(nodes, "Bộ luật Test", tier="leaf", header_mode="placebo")
    point = next(chunk for chunk in chunks if chunk.chunk_id == "T:D5.K1.a")
    assert point.text.startswith("[Bộ luật Test, Điều ")
    assert point.text.splitlines()[0] != point.citation
    assert point.citation == "[Bộ luật Test, Điều 5, Khoản 1, Điểm a]"


def test_chunks_sha256_is_stable_and_order_independent() -> None:
    nodes = sample_nodes()
    chunks = build_chunks(nodes, "Bộ luật Test", tier="leaf")
    assert chunks_sha256(chunks) == chunks_sha256(list(reversed(chunks)))
    assert len(chunks_sha256(chunks)) == 64