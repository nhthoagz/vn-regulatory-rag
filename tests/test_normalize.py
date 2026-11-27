from __future__ import annotations

import unicodedata

from src.common.normalize import (
    collapse_whitespace,
    fold_for_search,
    nfc,
    normalize_text,
    normalize_tones,
    strip_diacritics,
)


def test_nfc_composes_decomposed_input() -> None:
    decomposed = unicodedata.normalize("NFD", "Điều 98")
    assert nfc(decomposed) == "Điều 98"


def test_tone_moves_to_second_vowel_in_open_syllable() -> None:
    assert normalize_tones("hòa") == "hoà"
    assert normalize_tones("thúy") == "thuý"
    assert normalize_tones("khỏe") == "khoẻ"


def test_already_normalized_text_is_unchanged() -> None:
    for word in ["hoà", "thuý", "khoẻ", "quý"]:
        assert normalize_tones(word) == word


def test_closed_syllable_keeps_tone_where_it_is() -> None:
    # "khoảng" có phụ âm cuối nên dấu thanh bắt buộc nằm ở nguyên âm thứ hai.
    assert normalize_tones("khoảng") == "khoảng"
    assert normalize_tones("hoàn") == "hoàn"


def test_non_ambiguous_pairs_are_never_moved() -> None:
    # "ua", "ia", "ưa" không nhập nhằng: "của", "mùa", "chìa" phải giữ nguyên.
    for word in ["của", "mùa", "chìa", "quà"]:
        assert normalize_tones(word) == word


def test_uppercase_is_handled() -> None:
    assert normalize_tones("HÒA") == "HOÀ"


def test_strip_diacritics_removes_everything_including_d_stroke() -> None:
    assert strip_diacritics("Điều 98 khoản 1 điểm a") == "Dieu 98 khoan 1 diem a"
    assert strip_diacritics("Ứng dụng") == "Ung dung"


def test_fold_for_search_lowercases_and_strips() -> None:
    assert fold_for_search("  Điều   98 ") == "dieu 98"


def test_collapse_whitespace() -> None:
    assert collapse_whitespace("  a \n\t b  ") == "a b"


def test_normalize_text_composes_everything() -> None:
    assert normalize_text("  Điều  HÒA  ") == "Điều HOÀ"