# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import pytest

from rich_text_delta import _utf16

EMOJI = '\U0001f600'  # U+1F600, the surrogate pair D83D DE00
HIGH = '\ud83d'  # its leading half, on its own
LOW = '\ude00'  # its trailing half, on its own


class TestLength:
    @pytest.mark.parametrize(
        ('text', 'expected'),
        [
            ('', 0),
            ('abc', 3),
            ('中', 1),  # BMP, so one code unit despite three UTF-8 bytes
            (EMOJI, 2),
            (HIGH, 1),
            ('a' + EMOJI + 'b', 4),
            ('\U0001f1ec\U0001f1e7', 4),  # regional indicator flag
            ('\U0001f468\u200d\U0001f469', 5),  # ZWJ sequence
        ],
    )
    def test_counts_code_units(self, text: str, expected: int) -> None:
        assert _utf16.length(text) == expected


def _slice(text: str, start: int, end: int) -> str:
    """How `OpIterator` slices: over the code units of `text`."""
    return _utf16.slice_units(_utf16.units(text), start, end)


class TestSlice:
    def test_ascii(self) -> None:
        assert _slice('abcd', 1, 3) == 'bc'

    def test_before_a_pair(self) -> None:
        assert _slice('a' + EMOJI + 'b', 0, 1) == 'a'

    def test_across_a_whole_pair(self) -> None:
        assert _slice('a' + EMOJI + 'b', 1, 3) == EMOJI

    def test_splitting_a_pair_yields_a_lone_surrogate(self) -> None:
        assert _slice('a' + EMOJI + 'b', 0, 2) == 'a' + HIGH
        assert _slice('a' + EMOJI + 'b', 2, 4) == LOW + 'b'

    def test_lone_surrogate_input(self) -> None:
        assert _slice(HIGH + 'b', 0, 1) == HIGH

    def test_past_the_end_and_empty_range(self) -> None:
        assert _slice(EMOJI, 0, 5) == EMOJI
        assert _slice(EMOJI, 1, 1) == ''


class TestJoin:
    def test_recombines_a_split_pair(self) -> None:
        assert _utf16.join(HIGH, LOW) == EMOJI
        assert _utf16.join('a' + HIGH, LOW + 'b') == 'a' + EMOJI + 'b'

    @pytest.mark.parametrize(
        ('left', 'right'),
        [(HIGH, 'b'), ('a', LOW), (HIGH, ''), ('', LOW), ('a', 'b'), ('', '')],
    )
    def test_leaves_everything_else_concatenated(self, left: str, right: str) -> None:
        assert _utf16.join(left, right) == left + right


class TestRecompose:
    def test_composes_an_adjacent_pair(self) -> None:
        assert _utf16.recompose(HIGH + LOW) == EMOJI

    def test_preserves_a_lone_surrogate(self) -> None:
        assert _utf16.recompose(HIGH) == HIGH
        assert _utf16.recompose(LOW + 'b') == LOW + 'b'

    @pytest.mark.parametrize('text', ['', 'abc', '中', EMOJI, HIGH, 'a' + EMOJI + 'b'])
    def test_is_idempotent(self, text: str) -> None:
        assert _utf16.recompose(_utf16.recompose(text)) == _utf16.recompose(text)


class TestDecompose:
    def test_expands_astral_characters(self) -> None:
        assert _utf16.decompose('a' + EMOJI + 'b') == 'a' + HIGH + LOW + 'b'

    @pytest.mark.parametrize('text', ['', 'abc', '中', HIGH, EMOJI, 'a' + EMOJI + '中' + LOW])
    def test_one_character_per_code_unit(self, text: str) -> None:
        assert len(_utf16.decompose(text)) == _utf16.length(text)

    @pytest.mark.parametrize('text', ['', 'abc', '中', HIGH, EMOJI, 'a' + EMOJI + '中' + LOW])
    def test_round_trips_through_recompose(self, text: str) -> None:
        assert _utf16.recompose(_utf16.decompose(text)) == _utf16.recompose(text)


def _find(text: str, sub: str, start: int = 0) -> int:
    """How `OpIterator` searches: over the code units of `text`."""
    return _utf16.find_units(_utf16.units(text), _utf16.units(sub), start)


class TestFind:
    def test_ascii(self) -> None:
        assert _find('a\nb', '\n') == 1
        assert _find('abc', 'z') == -1

    def test_returns_a_code_unit_offset(self) -> None:
        assert _find('a' + EMOJI + '\n', '\n') == 3

    def test_ignores_a_match_that_is_not_code_unit_aligned(self) -> None:
        # These two characters encode to `00 0A 00 01`, where a plain byte search finds the
        # newline's `0A 00` at byte 1 and would report code unit 0.
        text = '\u0a00\u0100\n'
        assert _find(text, '\n') == 2

    def test_astral_needle(self) -> None:
        assert _find('xx' + EMOJI, EMOJI) == 2

    def test_lone_surrogate_needle_matches_inside_a_pair(self) -> None:
        # As in JavaScript, where the haystack is a code-unit sequence and each half of a
        # pair is findable on its own.
        assert _find('xx' + EMOJI, HIGH) == 2
        assert _find('xx' + EMOJI, LOW) == 3

    def test_start_offset(self) -> None:
        assert _find(EMOJI + '\n' + EMOJI + '\n', '\n', 3) == 5

    def test_clamps_a_negative_start(self) -> None:
        assert _find('a' + EMOJI, EMOJI, -5) == 1

    def test_empty_needle(self) -> None:
        assert _find('a' + EMOJI, '', 2) == 2
