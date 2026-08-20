# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""The surrogate handling in `_fast_diff`, which `Delta.diff` reaches only indirectly.

`_fast_diff` is a port of a library written against JavaScript strings, so it is given one
character per UTF-16 code unit — `_utf16.decompose` output. Its four surrogate-repair sites
only do anything on that input: on ordinary Python `str`, an astral character is a single
code point above the surrogate range and none of them ever fire.

What they buy is that no edit ever splits a surrogate pair, which
`test_splits_a_pair_without_the_repair` pins down by asking for the same diff with the repair
switched off.
"""

from __future__ import annotations

from typing import List, Optional

from rich_text_delta import _fast_diff, _utf16

EMOJI = '\U0001f600'  # D83D DE00
SAME_HIGH = '\U0001f601'  # D83D DE01, so it shares the leading surrogate
SAME_LOW = '\U0001fa00'  # D83E DE00, so it shares the trailing surrogate


def _diff(text1: str, text2: str, cursor: Optional[int] = None) -> List[_fast_diff.Diff]:
    return _fast_diff.diff(_utf16.decompose(text1), _utf16.decompose(text2), cursor, True)


def _unpaired(text: str) -> List[str]:
    """Every surrogate in ``text`` that is not part of a pair."""
    strays = []
    index = 0
    while index < len(text):
        code = ord(text[index])
        following = ord(text[index + 1]) if index + 1 < len(text) else 0
        if 0xD800 <= code <= 0xDBFF and 0xDC00 <= following <= 0xDFFF:
            index += 2
            continue
        if 0xD800 <= code <= 0xDFFF:
            strays.append(text[index])
        index += 1
    return strays


def _assert_pair_safe(components: List[_fast_diff.Diff], text1: str, text2: str) -> None:
    for _, text in components:
        assert _unpaired(text) == [], f'component {text!r} splits a surrogate pair'
    rebuilt1 = ''.join(text for op, text in components if op != _fast_diff.INSERT)
    rebuilt2 = ''.join(text for op, text in components if op != _fast_diff.DELETE)
    assert rebuilt1 == _utf16.decompose(text1)
    assert rebuilt2 == _utf16.decompose(text2)


class TestPairSafety:
    def test_emoji_sharing_the_leading_surrogate(self) -> None:
        # `_diff_common_prefix` finds a one-unit prefix and has to give it back.
        components = _diff(EMOJI, SAME_HIGH)
        _assert_pair_safe(components, EMOJI, SAME_HIGH)
        assert components == [
            (_fast_diff.DELETE, _utf16.decompose(EMOJI)),
            (_fast_diff.INSERT, _utf16.decompose(SAME_HIGH)),
        ]

    def test_emoji_sharing_the_trailing_surrogate(self) -> None:
        # The mirror image, in `_diff_common_suffix`.
        components = _diff(EMOJI, SAME_LOW)
        _assert_pair_safe(components, EMOJI, SAME_LOW)
        assert components == [
            (_fast_diff.DELETE, _utf16.decompose(EMOJI)),
            (_fast_diff.INSERT, _utf16.decompose(SAME_LOW)),
        ]

    def test_dropping_the_first_of_two_emoji_sharing_a_surrogate(self) -> None:
        # The example in `_diff_cleanup_merge`'s own comment: the equalities either side of
        # the change are stray halves, and get folded into it.
        components = _diff(EMOJI + SAME_HIGH, SAME_HIGH)
        _assert_pair_safe(components, EMOJI + SAME_HIGH, SAME_HIGH)

    def test_cursor_landing_inside_a_pair(self) -> None:
        # `_make_edit_splice` refuses the cursor fast path when the splice would cut a pair,
        # so this falls back to the full diff rather than emitting half of one.
        components = _diff(EMOJI, EMOJI + EMOJI, 1)
        _assert_pair_safe(components, EMOJI, EMOJI + EMOJI)

    def test_inserting_an_emoji_into_ascii(self) -> None:
        components = _diff('ab', 'a' + EMOJI + 'b')
        _assert_pair_safe(components, 'ab', 'a' + EMOJI + 'b')
        assert components == [
            (_fast_diff.EQUAL, 'a'),
            (_fast_diff.INSERT, _utf16.decompose(EMOJI)),
            (_fast_diff.EQUAL, 'b'),
        ]

    def test_splits_a_pair_without_the_repair(self) -> None:
        """Without `fix_unicode` the same diff cuts the pair — so the repair is load-bearing."""
        unrepaired = _fast_diff._diff_main(
            _utf16.decompose(EMOJI), _utf16.decompose(SAME_HIGH), None, True, False
        )
        assert [op for op, _ in unrepaired] == [
            _fast_diff.EQUAL,
            _fast_diff.DELETE,
            _fast_diff.INSERT,
        ]
        assert _unpaired(unrepaired[0][1]) == ['\ud83d']
