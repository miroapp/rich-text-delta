# SPDX-License-Identifier: Apache-2.0
#
# The cursor fast path and the surrogate handling below are ported from fast-diff
# (https://github.com/jhchen/fast-diff), the JavaScript dependency the TypeScript
# implementation uses for Delta.diff(). fast-diff modifies the diff-match-patch library by
# Neil Fraser by removing the patch and match functionality and adding, among other things,
# those two. The original license is as follows:
#
# ===
#
# Diff Match and Patch
#
# Copyright 2006 Google Inc.
# http://code.google.com/p/google-diff-match-patch/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Character diff, from the `diff-match-patch` package.

`Delta.diff` needs what the TypeScript implementation gets from the `fast-diff` npm
package, which is Diff Match and Patch with the patch and match halves removed. The PyPI
`diff-match-patch` package is the same library with those halves still attached, so the
diff comes straight from it; what fast-diff adds on top and this module reproduces is the
cursor-position fast path and the surrogate-pair awareness below.

The data structure representing a diff is a list of tuples::

    [(DELETE, 'Hello'), (INSERT, 'Goodbye'), (EQUAL, ' world.')]

which means: delete 'Hello', add 'Goodbye' and keep ' world.'.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple, Union

from diff_match_patch import diff_match_patch

DELETE = diff_match_patch.DIFF_DELETE
INSERT = diff_match_patch.DIFF_INSERT
EQUAL = diff_match_patch.DIFF_EQUAL

Diff = Tuple[int, str]
CursorRange = Any  # {'index': int, 'length': int}
CursorPos = Union[int, Any]

_Edit = List[str]  # [deleted, inserted], mutable while the pairs are being repaired

_UNPATCHED = diff_match_patch()
"""Kept aside so the overrides below can still reach the trimming they wrap."""


def diff(
    text1: str,
    text2: str,
    cursor_pos: Optional[CursorPos] = None,
    cleanup: bool = False,
) -> List[Diff]:
    """Find the differences between two texts.

    ``cursor_pos`` is an edit position in ``text1``, or a mapping with more info:
    ``{'oldRange': {'index': int, 'length': int}, 'newRange': {...} | None}``.
    ``cleanup`` applies semantic cleanup before returning.
    """
    if text1 == text2:
        return [(EQUAL, text1)] if text1 else []

    if cursor_pos is not None:
        editdiff = _find_cursor_edit_diff(text1, text2, cursor_pos)
        if editdiff is not None:
            return editdiff

    differ = _new_differ()
    diffs = differ.diff_main(text1, text2, False)
    if cleanup:
        differ.diff_cleanupSemantic(diffs)
    _repair_pairs(differ, diffs)
    return [(op, text) for op, text in diffs]


def _new_differ() -> Any:
    """A ``diff_match_patch`` that is deterministic and knows about surrogate pairs.

    ``diff_commonPrefix`` and ``diff_commonSuffix`` are replaced per instance rather than
    by subclassing: the package ships no type information, so a subclass of it would be a
    subclass of ``Any``. Diff Match and Patch reaches them through ``self``, so overriding
    them here covers the trimming in ``diff_main`` and in the cleanup passes alike.
    """
    differ = diff_match_patch()
    # A deadline that never arrives, so the diff does not vary with how fast the machine
    # running it happens to be. Not `0`, the package's own spelling of "no timeout" — that
    # also turns off the half-match speedup.
    differ.Diff_Timeout = float('inf')
    differ.diff_commonPrefix = _common_prefix
    differ.diff_commonSuffix = _common_suffix
    return differ


def _char_code_at(text: str, index: int) -> int:
    """``text.charCodeAt(index)``: out of range is ``NaN``, which fails every comparison."""
    if 0 <= index < len(text):
        return ord(text[index])
    return -1


def _common_prefix(text1: str, text2: str) -> int:
    """The number of characters common to the start of each string, minus a stray half.

    Trimming a prefix that ends between a high surrogate and its low half would leave both
    the equality and the edit after it holding an unpaired half, so give the half back.
    """
    length = _UNPATCHED.diff_commonPrefix(text1, text2)
    if _is_surrogate_pair_start(_char_code_at(text1, length - 1)):
        length -= 1
    return length


def _common_suffix(text1: str, text2: str) -> int:
    """The number of characters common to the end of each string, minus a stray half."""
    length = _UNPATCHED.diff_commonSuffix(text1, text2)
    if _is_surrogate_pair_end(_char_code_at(text1, len(text1) - length)):
        length -= 1
    return length


def _repair_pairs(differ: Any, diffs: List[Any]) -> None:
    """Put back together every surrogate pair a component boundary cut in half.

    ``_utf16.decompose`` gives the diff one character per code unit, so a boundary can fall
    between a high surrogate and its low half, and then the components either side of it
    each hold an unpaired half. Moving the stray half off the equality and into the edit
    beside it brings the pair back inside one component; ``diff_cleanupMerge`` then factors
    out whatever prefix or suffix that made common, and drops whatever it emptied.

    Shaving and re-merging can undo one another — a stray with no partner in the diff at
    all goes straight back where it came from — so this stops as soon as a round changes
    nothing rather than assuming one pass will settle it.
    """
    while True:
        before = list(diffs)
        equalities, edits = _split_edits(diffs)
        _shave_strays(equalities, edits)
        diffs[:] = _join_edits(equalities, edits)
        differ.diff_cleanupMerge(diffs)
        if list(diffs) == before:
            return


def _split_edits(diffs: List[Any]) -> Tuple[List[str], List[_Edit]]:
    """``diffs`` as equalities separated by edits, one equality more than there are edits.

    Collapsing each run of deletions and insertions into a single ``[deleted, inserted]``
    pair is what makes the shaving below a local rewrite.
    """
    equalities = ['']
    edits: List[_Edit] = []
    for op, text in diffs:
        if op == EQUAL:
            if len(equalities) == len(edits):
                equalities.append(text)
            else:
                equalities[-1] += text
        else:
            if len(equalities) > len(edits):
                edits.append(['', ''])
            edits[-1][0 if op == DELETE else 1] += text
    if len(equalities) == len(edits):
        equalities.append('')
    return equalities, edits


def _shave_strays(equalities: List[str], edits: List[_Edit]) -> None:
    """Move every surrogate half stranded at an equality's edge into the edit beside it.

    The half goes into both sides of the edit, since it is text both streams have at that
    point: only the boundary between the components was in the wrong place.
    """
    for index, edit in enumerate(edits):
        before = equalities[index]
        if _ends_with_pair_start(before):
            equalities[index] = before[:-1]
            edit[0] = before[-1] + edit[0]
            edit[1] = before[-1] + edit[1]
        after = equalities[index + 1]
        if _starts_with_pair_end(after):
            equalities[index + 1] = after[1:]
            edit[0] += after[0]
            edit[1] += after[0]


def _join_edits(equalities: List[str], edits: List[_Edit]) -> List[Diff]:
    """The inverse of :func:`_split_edits`, dropping whatever the shaving emptied out."""
    diffs = []
    for index, equality in enumerate(equalities):
        if equality:
            diffs.append((EQUAL, equality))
        if index < len(edits):
            deleted, inserted = edits[index]
            if deleted:
                diffs.append((DELETE, deleted))
            if inserted:
                diffs.append((INSERT, inserted))
    return diffs


def _is_surrogate_pair_start(char_code: int) -> bool:
    return 0xD800 <= char_code <= 0xDBFF


def _is_surrogate_pair_end(char_code: int) -> bool:
    return 0xDC00 <= char_code <= 0xDFFF


def _starts_with_pair_end(text: str) -> bool:
    return _is_surrogate_pair_end(_char_code_at(text, 0))


def _ends_with_pair_start(text: str) -> bool:
    return _is_surrogate_pair_start(_char_code_at(text, len(text) - 1))


def _make_edit_splice(
    before: str, old_middle: str, new_middle: str, after: str
) -> Optional[List[Diff]]:
    if _ends_with_pair_start(before) or _starts_with_pair_end(after):
        return None
    return [
        (op, text)
        for op, text in (
            (EQUAL, before),
            (DELETE, old_middle),
            (INSERT, new_middle),
            (EQUAL, after),
        )
        if text
    ]


_BREAK = object()
"""Leaving a labelled block, as opposed to returning from the function."""


def _find_cursor_edit_diff(
    old_text: str, new_text: str, cursor_pos: CursorPos
) -> Optional[List[Diff]]:
    # note: this runs after equality check has ruled out exact equality
    old_range = (
        {'index': cursor_pos, 'length': 0}
        if isinstance(cursor_pos, int)
        else cursor_pos['oldRange']
    )
    new_range = None if isinstance(cursor_pos, int) else cursor_pos.get('newRange')
    # take into account the old and new selection to generate the best diff
    # possible for a text edit. for example, a text change from "xxx" to "xx"
    # could be a delete or forwards-delete of any one of the x's, or the
    # result of selecting two of the x's and typing "x".
    old_length = len(old_text)
    new_length = len(new_text)
    if old_range['length'] == 0 and (new_range is None or new_range['length'] == 0):
        # see if we have an insert or delete before or after cursor
        old_cursor = old_range['index']
        old_before = old_text[:old_cursor]
        old_after = old_text[old_cursor:]
        maybe_new_cursor = new_range['index'] if new_range else None

        def edit_before() -> Any:
            # is this an insert or delete right before old_cursor?
            new_cursor = old_cursor + new_length - old_length
            if maybe_new_cursor is not None and maybe_new_cursor != new_cursor:
                return _BREAK
            if new_cursor < 0 or new_cursor > new_length:
                return _BREAK
            new_before = new_text[:new_cursor]
            new_after = new_text[new_cursor:]
            if new_after != old_after:
                return _BREAK
            prefix_length = min(old_cursor, new_cursor)
            old_prefix = old_before[:prefix_length]
            new_prefix = new_before[:prefix_length]
            if old_prefix != new_prefix:
                return _BREAK
            old_middle = old_before[prefix_length:]
            new_middle = new_before[prefix_length:]
            return _make_edit_splice(old_prefix, old_middle, new_middle, old_after)

        def edit_after() -> Any:
            # is this an insert or delete right after old_cursor?
            if maybe_new_cursor is not None and maybe_new_cursor != old_cursor:
                return _BREAK
            cursor = old_cursor
            new_before = new_text[:cursor]
            new_after = new_text[cursor:]
            if new_before != old_before:
                return _BREAK
            suffix_length = min(old_length - cursor, new_length - cursor)
            old_suffix = old_after[len(old_after) - suffix_length :]
            new_suffix = new_after[len(new_after) - suffix_length :]
            if old_suffix != new_suffix:
                return _BREAK
            old_middle = old_after[: len(old_after) - suffix_length]
            new_middle = new_after[: len(new_after) - suffix_length]
            return _make_edit_splice(old_before, old_middle, new_middle, old_suffix)

        result = edit_before()
        if result is not _BREAK:
            return result
        result = edit_after()
        if result is not _BREAK:
            return result

    if old_range['length'] > 0 and new_range and new_range['length'] == 0:
        # see if diff could be a splice of the old selection range
        old_prefix = old_text[: old_range['index']]
        old_suffix = old_text[old_range['index'] + old_range['length'] :]
        prefix_length = len(old_prefix)
        suffix_length = len(old_suffix)
        if new_length < prefix_length + suffix_length:
            return None
        new_prefix = new_text[:prefix_length]
        new_suffix = new_text[new_length - suffix_length :]
        if old_prefix != new_prefix or old_suffix != new_suffix:
            return None
        old_middle = old_text[prefix_length : old_length - suffix_length]
        new_middle = new_text[prefix_length : new_length - suffix_length]
        return _make_edit_splice(old_prefix, old_middle, new_middle, old_suffix)

    return None
