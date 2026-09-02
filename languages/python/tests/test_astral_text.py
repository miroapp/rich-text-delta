# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""Astral text end to end: positions in code units, and text in canonical form.

Every expectation below was taken from the TypeScript reference (`dist/index.cjs` under
node), so these are interoperability tests rather than a restatement of this port's own
behaviour. The declarative corpus covers the same ground for `compose`, `length` and `slice`;
what it cannot express is `each_line` and the canonical-form invariant, and it has no astral
`diff` cases yet.
"""

from __future__ import annotations

from typing import Any, Dict, List

from rich_text_delta import Delta, Op, _utf16

EMOJI = '\U0001f600'  # D83D DE00
SAME_HIGH = '\U0001f601'  # D83D DE01
SAME_LOW = '\U0001fa00'  # D83E DE00
HIGH = '\ud83d'
LOW = '\ude00'


def _lines(delta: Delta, *args: str) -> List[List[Op]]:
    collected: List[List[Op]] = []

    def collect(line: Delta, _attributes: Dict[str, Any], _index: int) -> None:
        collected.append(line.ops)

    delta.each_line(collect, *args)
    return collected


class TestPositionsAreCodeUnits:
    def test_length_counts_an_emoji_as_two(self) -> None:
        assert Delta().insert('a' + EMOJI + 'b').length() == 4

    def test_transform_position_skips_both_units(self) -> None:
        assert Delta().insert(EMOJI).transform_position(0) == 2

    def test_compose_formats_one_unit_of_an_emoji(self) -> None:
        composed = (
            Delta().insert('a' + EMOJI + 'b').compose(Delta().retain(2).retain(1, {'bold': True}))
        )
        assert composed.ops == [
            {'insert': 'a' + HIGH},
            {'insert': LOW, 'attributes': {'bold': True}},
            {'insert': 'b'},
        ]

    def test_slice_splits_a_pair(self) -> None:
        assert Delta().insert(EMOJI).slice(0, 1).ops == [{'insert': HIGH}]
        assert Delta().insert('a' + EMOJI + 'b').slice(2, 4).ops == [{'insert': LOW + 'b'}]

    def test_invert_of_a_mid_pair_format(self) -> None:
        change = Delta().retain(2).retain(1, {'bold': True})
        assert change.invert(Delta().insert('a' + EMOJI + 'b')).ops == [
            {'retain': 2},
            {'retain': 1, 'attributes': {'bold': None}},
        ]

    def test_transform_of_a_mid_pair_format(self) -> None:
        change = Delta().retain(2).retain(1, {'bold': True})
        other = Delta().retain(2).retain(1, {'italic': True})
        assert change.transform(other, True) == Delta(
            [{'retain': 2}, {'retain': 1, 'attributes': {'italic': True}}]
        )


class TestCanonicalForm:
    def test_push_rejoins_a_split_pair(self) -> None:
        assert Delta().insert('a' + HIGH).insert(LOW + 'b').ops == [{'insert': 'a' + EMOJI + 'b'}]

    def test_push_canonicalizes_incoming_text(self) -> None:
        assert Delta().push({'insert': HIGH + LOW}).ops == [{'insert': EMOJI}]

    def test_insert_canonicalizes_incoming_text(self) -> None:
        assert Delta().insert('a' + HIGH + LOW).ops == [{'insert': 'a' + EMOJI}]

    def test_results_hold_canonical_text(self) -> None:
        document = Delta().insert('a' + EMOJI + 'b' + SAME_HIGH)
        change = Delta().retain(2).retain(3, {'bold': True})
        results = [
            document.compose(change),
            document.slice(1, 5),
            document.diff(Delta().insert('a' + EMOJI + 'b')),
            change.invert(document),
            document.concat(Delta().insert(EMOJI)),
        ]
        for delta in results:
            for op in delta.ops:
                insert = op.get('insert')
                if isinstance(insert, str):
                    assert insert == _utf16.recompose(insert), f'not canonical: {insert!r}'


class TestEachLine:
    def test_lines_around_astral_text(self) -> None:
        delta = Delta().insert('a' + EMOJI + '\nb' + EMOJI + 'c\n')
        assert _lines(delta) == [
            [{'insert': 'a' + EMOJI}],
            [{'insert': 'b' + EMOJI + 'c'}],
        ]

    def test_an_astral_separator_consumes_one_code_unit(self) -> None:
        # Faithful to the reference, which advances by one code unit past the separator and
        # so leaves its trailing half at the head of the next line.
        delta = Delta().insert('a' + EMOJI + 'b' + EMOJI + 'c')
        assert _lines(delta, EMOJI) == [
            [{'insert': 'a'}],
            [{'insert': LOW + 'b'}],
            [{'insert': LOW + 'c'}],
        ]


class TestDiff:
    def test_emoji_sharing_the_leading_surrogate(self) -> None:
        result = Delta().insert(EMOJI).diff(Delta().insert(SAME_HIGH))
        assert result.ops == [{'insert': SAME_HIGH}, {'delete': 2}]

    def test_emoji_sharing_the_trailing_surrogate(self) -> None:
        result = Delta().insert(EMOJI).diff(Delta().insert(SAME_LOW))
        assert result.ops == [{'insert': SAME_LOW}, {'delete': 2}]

    def test_inserting_an_emoji(self) -> None:
        result = Delta().insert('ab').diff(Delta().insert('a' + EMOJI + 'b'))
        assert result.ops == [{'retain': 1}, {'insert': EMOJI}]

    def test_a_pair_split_across_two_ops_is_one_character_of_text(self) -> None:
        # The halves live in different ops, but the document's text is one emoji, so this is
        # an attribute change rather than a rewrite.
        # Constructed directly: `push` would rejoin the halves into one op.
        document = Delta([{'insert': 'a' + HIGH}, {'insert': LOW + 'b'}])
        other = Delta().insert('a' + EMOJI + 'b', {'bold': True})
        assert document.diff(other).ops == [{'retain': 4, 'attributes': {'bold': True}}]
