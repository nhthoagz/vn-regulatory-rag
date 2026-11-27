"""Chuẩn hóa text dùng chung cho ingest và retrieval."""

from __future__ import annotations

import re
import unicodedata

WHITESPACE_RE = re.compile(r"\s+")
LETTER_RE = re.compile(r"[^\W\d_]+")

VOWELS = frozenset("aeiouyAEIOUY")
# Các cặp nguyên âm mà vị trí dấu thanh thay đổi theo quy ước (hòa / hoà).
# Chỉ ba cặp này là nhập nhằng thật; "ua", "ia", "ưa" thì không (của, mùa, chìa).
AMBIGUOUS_PAIRS = frozenset({("o", "a"), ("o", "e"), ("u", "y")})

TONE_MARKS = frozenset({"\u0300", "\u0301", "\u0303", "\u0309", "\u0323"})
D_STROKE = "đ"
D_STROKE_UPPER = "Đ"


def nfc(text: str) -> str:
    """Chuẩn hóa Unicode NFC."""
    return unicodedata.normalize("NFC", text)


def collapse_whitespace(text: str) -> str:
    """Gộp mọi khoảng trắng/xuống dòng thành một dấu cách."""
    return WHITESPACE_RE.sub(" ", text).strip()


def strip_diacritics(text: str) -> str:
    """Bỏ toàn bộ dấu, kể cả đ/Đ -> d/D. Dùng cho tìm kiếm không dấu."""
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.replace(D_STROKE, "d").replace(D_STROKE_UPPER, "D")


def _units(word: str) -> list[list[str]]:
    """Tách word (đã NFD) thành [ký tự gốc, các dấu đi kèm]."""
    units: list[list[str]] = []
    for ch in word:
        if unicodedata.combining(ch):
            if not units:
                units.append(["", [ch]])
            else:
                units[-1][1].append(ch)
        else:
            units.append([ch, []])
    return units


def _rebuild(units: list[list[str]]) -> str:
    return "".join(base + "".join(marks) for base, marks in units)


def _fix_word(match: re.Match[str]) -> str:
    word = match.group(0)
    units = _units(unicodedata.normalize("NFD", word))
    vowel_idx = [i for i, (base, _) in enumerate(units) if base in VOWELS]
    if not vowel_idx:
        return word

    clusters: list[list[int]] = []
    for idx in vowel_idx:
        if clusters and idx == clusters[-1][-1] + 1:
            clusters[-1].append(idx)
        else:
            clusters.append([idx])
    cluster = clusters[-1]
    if len(cluster) != 2 or cluster[-1] != len(units) - 1:
        return word

    first, second = cluster
    pair = (units[first][0].lower(), units[second][0].lower())
    if pair not in AMBIGUOUS_PAIRS:
        return word

    tones_first = [m for m in units[first][1] if m in TONE_MARKS]
    if not tones_first:
        return word
    units[first][1] = [m for m in units[first][1] if m not in TONE_MARKS]
    units[second][1] = units[second][1] + tones_first[:1] + tones_first[1:]
    return unicodedata.normalize("NFC", _rebuild(units))


def normalize_tones(text: str) -> str:
    """Đưa mọi cách đặt dấu thanh về một quy ước (dấu ở nguyên âm thứ hai)."""
    return LETTER_RE.sub(_fix_word, text)


def normalize_text(text: str) -> str:
    """Chuẩn hóa đầy đủ cho text OCR: NFC, dấu thanh, khoảng trắng."""
    return collapse_whitespace(normalize_tones(nfc(text)))


def fold_for_search(text: str) -> str:
    """Dạng dùng cho chỉ mục không dấu: NFC -> bỏ dấu -> lowercase -> gộp trắng."""
    return collapse_whitespace(strip_diacritics(nfc(text)).lower())