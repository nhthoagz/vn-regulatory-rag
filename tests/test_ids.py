from __future__ import annotations

import pytest

from src.common.ids import (
    Level,
    make_article_id,
    make_chapter_id,
    make_clause_id,
    make_point_id,
    make_section_id,
    make_table_id,
    parse_node_id,
)

DOC = "45-2019-QH14"


def test_article_id_round_trip() -> None:
    node_id = make_article_id(DOC, "98")
    parsed = parse_node_id(node_id)
    assert node_id == "45-2019-QH14:D98"
    assert parsed.doc_id == DOC
    assert parsed.level is Level.article
    assert parsed.article == "98"
    assert parsed.clause is None


def test_article_with_letter_suffix() -> None:
    parsed = parse_node_id(make_article_id(DOC, "2a"))
    assert parsed.article == "2a"
    assert parsed.level is Level.article


def test_clause_and_point_ids() -> None:
    clause_id = make_clause_id(DOC, "98", 1)
    point_id = make_point_id(DOC, "98", 1, "a")
    assert clause_id == "45-2019-QH14:D98.K1"
    assert point_id == "45-2019-QH14:D98.K1.a"

    clause = parse_node_id(clause_id)
    point = parse_node_id(point_id)
    assert clause.level is Level.clause
    assert clause.clause == 1
    assert point.level is Level.point
    assert point.article == "98"
    assert point.clause == 1
    assert point.point == "a"


def test_point_d_with_stroke() -> None:
    parsed = parse_node_id(make_point_id(DOC, "98", 1, "đ"))
    assert parsed.point == "đ"


def test_chapter_and_section_ids() -> None:
    chapter = parse_node_id(make_chapter_id(DOC, "XVII"))
    section = parse_node_id(make_section_id(DOC, "IV", 2))
    assert chapter.level is Level.chapter
    assert chapter.chapter == "XVII"
    assert section.level is Level.section
    assert section.chapter == "IV"
    assert section.section == 2


def test_table_id_round_trip() -> None:
    parent = make_clause_id(DOC, "105", 3)
    table_id = make_table_id(parent, 2)
    assert table_id == "45-2019-QH14:D105.K3.T2"
    parsed = parse_node_id(table_id)
    assert parsed.level is Level.table
    assert parsed.table == 2


def test_invalid_ids_raise() -> None:
    for bad in ["", "45-2019-QH14", "45-2019-QH14:D", "45-2019-QH14:K1", "45-2019-QH14:D98.z"]:
        with pytest.raises(ValueError):
            parse_node_id(bad)


def test_point_without_clause_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_node_id("45-2019-QH14:D98.a")


def test_invalid_point_char_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_point_id(DOC, "98", 1, "z")