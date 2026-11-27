"""Sinh và phân tích node_id.

Định dạng (SPEC §5):
    {doc_id}:D{article}                      -> Điều
    {doc_id}:D{article}.K{clause}            -> Khoản
    {doc_id}:D{article}.K{clause}.{point}    -> Điểm
    {doc_id}:C{roman}                        -> Chương
    {doc_id}:C{roman}.M{section}             -> Mục
    {parent_id}.T{index}                     -> Bảng
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

ARTICLE_RE = re.compile(r"^(\d+)([a-zđ]?)$")
CHAPTER_RE = re.compile(r"^[IVXLC]+$")
POINTS = "abcdđeghiklmnopqrstuvxy"

ARTICLE_ID_RE = re.compile(
    r"D(?P<article>\d+[a-zđ]?)"
    r"(?:\.K(?P<clause>\d+))?"
    r"(?:\.(?P<point>[abcdđeghiklmnopqrstuvxy]))?"
    r"(?:\.T(?P<table>\d+))?"
)
CHAPTER_ID_RE = re.compile(r"C(?P<chapter>[IVXLC]+)(?:\.M(?P<section>\d+))?")

SEPARATOR = ":"


class Level(StrEnum):
    chapter = "chapter"
    section = "section"
    article = "article"
    clause = "clause"
    point = "point"
    table = "table"


@dataclass(frozen=True)
class ParsedId:
    """Kết quả phân tích node_id."""

    doc_id: str
    level: Level
    article: str | None = None
    clause: int | None = None
    point: str | None = None
    chapter: str | None = None
    section: int | None = None
    table: int | None = None


def make_article_id(doc_id: str, article: str) -> str:
    return f"{doc_id}{SEPARATOR}D{_check_article(article)}"


def make_clause_id(doc_id: str, article: str, clause: int) -> str:
    return f"{doc_id}{SEPARATOR}D{_check_article(article)}.K{_check_positive(clause, 'clause')}"


def make_point_id(doc_id: str, article: str, clause: int, point: str) -> str:
    if point not in POINTS:
        raise ValueError(f"point phải là một trong {POINTS!r}, nhận {point!r}")
    return f"{make_clause_id(doc_id, article, clause)}.{point}"


def make_chapter_id(doc_id: str, roman: str) -> str:
    if not CHAPTER_RE.match(roman):
        raise ValueError(f"chương phải là số La Mã, nhận {roman!r}")
    return f"{doc_id}{SEPARATOR}C{roman}"


def make_section_id(doc_id: str, roman: str, section: int) -> str:
    return f"{make_chapter_id(doc_id, roman)}.M{_check_positive(section, 'section')}"


def make_table_id(parent_id: str, index: int) -> str:
    return f"{parent_id}.T{_check_positive(index, 'index')}"


def parse_node_id(node_id: str) -> ParsedId:
    doc_id, sep, rest = node_id.partition(SEPARATOR)
    if not sep or not doc_id or not rest:
        raise ValueError(f"node_id không hợp lệ: {node_id!r}")

    if rest.startswith("D"):
        match = ARTICLE_ID_RE.fullmatch(rest)
        if not match:
            raise ValueError(f"phần Điều không hợp lệ: {node_id!r}")
        article = match.group("article")
        clause_raw = match.group("clause")
        point = match.group("point")
        table_raw = match.group("table")
        clause = int(clause_raw) if clause_raw else None
        table = int(table_raw) if table_raw else None
        if table is not None:
            level = Level.table
        elif point is not None:
            level = Level.point
        elif clause is not None:
            level = Level.clause
        else:
            level = Level.article
        if point is not None and clause is None:
            raise ValueError(f"điểm phải thuộc một khoản: {node_id!r}")
        return ParsedId(
            doc_id=doc_id,
            level=level,
            article=article,
            clause=clause,
            point=point,
            table=table,
        )

    if rest.startswith("C"):
        match = CHAPTER_ID_RE.fullmatch(rest)
        if not match:
            raise ValueError(f"phần Chương không hợp lệ: {node_id!r}")
        section_raw = match.group("section")
        return ParsedId(
            doc_id=doc_id,
            level=Level.section if section_raw else Level.chapter,
            chapter=match.group("chapter"),
            section=int(section_raw) if section_raw else None,
        )

    raise ValueError(f"node_id không hợp lệ: {node_id!r}")


def _check_article(article: str) -> str:
    if not ARTICLE_RE.match(article):
        raise ValueError(f"số Điều không hợp lệ: {article!r}")
    return article


def _check_positive(value: int, name: str) -> int:
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} phải là số nguyên >= 1, nhận {value!r}")
    return value