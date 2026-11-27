from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.common.ids import Level, make_clause_id, make_point_id
from src.common.schema import Node, citation_label

TITLE = "Bộ luật Lao động 2019"


def make_point_node() -> Node:
    return Node(
        node_id=make_point_id("45-2019-QH14", "98", 1, "a"),
        doc_id="45-2019-QH14",
        level=Level.point,
        article="98",
        clause=1,
        point="a",
        text="Người lao động làm thêm giờ vào ngày lễ được trả ít nhất 300%.",
        lead_in="Mức ít nhất 150% vào ngày thường.",
        page_span=(21, 21),
    )


def test_node_accepts_consistent_data() -> None:
    node = make_point_node()
    assert node.level is Level.point
    assert node.status == "active"
    assert node.has_exception is False


def test_level_must_match_node_id() -> None:
    with pytest.raises(ValidationError):
        Node(node_id=make_clause_id("45-2019-QH14", "98", 1), doc_id="45-2019-QH14", level="point")


def test_doc_id_must_match_node_id() -> None:
    with pytest.raises(ValidationError):
        Node(
            node_id=make_clause_id("45-2019-QH14", "98", 1),
            doc_id="18-VBHN-VPQH-2026",
            level="clause",
        )


def test_article_must_match_node_id() -> None:
    with pytest.raises(ValidationError):
        Node(
            node_id=make_clause_id("45-2019-QH14", "98", 1),
            doc_id="45-2019-QH14",
            level="clause",
            article="99",
        )


def test_invalid_page_span_is_rejected() -> None:
    node = make_point_node()
    with pytest.raises(ValidationError):
        Node(**{**node.model_dump(), "page_span": (5, 4)})


def test_node_is_json_round_trippable() -> None:
    node = make_point_node()
    restored = Node.model_validate_json(node.model_dump_json())
    assert restored == node


def test_citation_label_formats_point() -> None:
    expected = "[Bộ luật Lao động 2019, Điều 98, Khoản 1, Điểm a]"
    assert citation_label(make_point_node(), TITLE) == expected


def test_citation_label_formats_article_only() -> None:
    node = Node(node_id="45-2019-QH14:D98", doc_id="45-2019-QH14", level="article", article="98")
    assert citation_label(node, TITLE) == "[Bộ luật Lao động 2019, Điều 98]"