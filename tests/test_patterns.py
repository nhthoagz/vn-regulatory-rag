from __future__ import annotations

from src.ingest.patterns import (
    article_key,
    has_exception,
    is_cut_marker,
    match_article,
    match_chapter,
    match_clause,
    match_point,
)


def test_chapter_with_roman_numeral_only() -> None:
    assert match_chapter("Chương I") == ("I", None)
    assert match_chapter("Chương XII") == ("XII", None)


def test_chapter_with_inline_title() -> None:
    found = match_chapter("Chương VII GIỜ LÀM VIỆC VÀ THỜI GIỜ NGHỈ NGƠI")
    assert found == ("VII", "GIỜ LÀM VIỆC VÀ THỜI GIỜ NGHỈ NGƠI")


def test_chapter_body_sentence_is_not_a_chapter() -> None:
    # Dòng nội dung thật trong văn bản (Điều 104), không phải tiêu đề chương.
    assert match_chapter("Chương trình an toàn, vệ sinh lao động tại nơi làm việc") is None


def test_article_requires_capital_d_and_a_period() -> None:
    assert match_article("Điều 98. Mức làm thêm giờ") == ("98", "Mức làm thêm giờ")
    assert match_article("Điều 2a. Thời gian thử việc") == ("2a", "Thời gian thử việc")
    assert match_article("điều 98. không phải tiêu đề") is None
    assert match_article("Điều 98 Mức làm thêm giờ") is None


def test_clause_accepts_dot_and_ocr_comma() -> None:
    assert match_clause("1. Người lao động") == (1, "Người lao động")
    assert match_clause("1, Thời gian làm việc") == (1, "Thời gian làm việc")


def test_clause_rejects_money_like_number() -> None:
    assert match_clause("1.000.000 đồng") is None


def test_list_continuation_matches_regex_so_parser_must_guard() -> None:
    # Regex vẫn khớp; parser chặn bằng điều kiện số khoản phải tuần tự.
    assert match_clause("104, 118 và khoản 1 Điều 128") == (104, "118 và khoản 1 Điều 128")


def test_point_letters() -> None:
    assert match_point("a) Làm việc theo hợp đồng") == ("a", "Làm việc theo hợp đồng")
    assert match_point("đ) Trường hợp khác") == ("đ", "Trường hợp khác")
    assert match_point("3) Không phải điểm") is None


def test_cut_markers() -> None:
    assert is_cut_marker("MỤC LỤC")
    assert is_cut_marker("Nơi nhận:")
    assert not is_cut_marker("Điều 1. Phạm vi điều chỉnh")


def test_has_exception_finds_exclusion_clauses() -> None:
    assert has_exception("trừ trường hợp quy định tại khoản 3 Điều này")
    assert has_exception("áp dụng cho mọi đối tượng, ngoại trừ người nước ngoài")
    assert has_exception("quy định này không áp dụng đối với lao động thời vụ")


def test_has_exception_ignores_deduction() -> None:
    # "khấu trừ" là khấu trừ tiền lương (Điều 102), không phải mệnh đề loại trừ.
    assert has_exception("Người sử dụng lao động được khấu trừ tiền lương") is False
    assert has_exception("Người lao động làm việc theo hợp đồng lao động") is False


def test_article_key_ordering() -> None:
    assert article_key("2") < article_key("2a") < article_key("3")
    assert article_key("10") > article_key("9")