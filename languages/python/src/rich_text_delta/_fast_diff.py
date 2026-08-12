# SPDX-License-Identifier: Apache-2.0
#
# A Python port of fast-diff (https://github.com/jhchen/fast-diff), the JavaScript
# dependency the TypeScript implementation uses for Delta.diff(). fast-diff itself
# modifies the diff-patch-match library by Neil Fraser by removing the patch and match
# functionality and certain advanced options in the diff function. The original license
# is as follows:
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

"""Character diff, ported from fast-diff.

The data structure representing a diff is a list of tuples::

    [(DELETE, 'Hello'), (INSERT, 'Goodbye'), (EQUAL, ' world.')]

which means: delete 'Hello', add 'Goodbye' and keep ' world.'.
"""

from __future__ import annotations

import math
import re
from typing import Any, List, Optional, Tuple, Union

DELETE = -1
INSERT = 1
EQUAL = 0

Diff = Tuple[int, str]
CursorRange = Any  # {'index': int, 'length': int}
CursorPos = Union[int, Any]

_Tuple = List[Any]  # [op, text], mutable while the diff is being built


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
    # only pass fix_unicode=True at the top level, not when _diff_main is
    # recursively invoked
    return [(op, text) for op, text in _diff_main(text1, text2, cursor_pos, cleanup, True)]


def _char_at(text: str, index: int) -> str:
    """``text.charAt(index)``: out of range is the empty string, and never wraps."""
    if 0 <= index < len(text):
        return text[index]
    return ''


def _char_code_at(text: str, index: int) -> int:
    """``text.charCodeAt(index)``: out of range is ``NaN``, which fails every comparison."""
    if 0 <= index < len(text):
        return ord(text[index])
    return -1


def _diff_main(
    text1: str,
    text2: str,
    cursor_pos: Optional[CursorPos] = None,
    cleanup: bool = False,
    fix_unicode: bool = False,
) -> List[_Tuple]:
    """Find the differences between two texts.

    Simplifies the problem by stripping any common prefix or suffix off the texts before
    diffing.
    """
    # Check for equality
    if text1 == text2:
        if text1:
            return [[EQUAL, text1]]
        return []

    if cursor_pos is not None:
        editdiff = _find_cursor_edit_diff(text1, text2, cursor_pos)
        if editdiff is not None:
            return editdiff

    # Trim off common prefix (speedup).
    commonlength = _diff_common_prefix(text1, text2)
    commonprefix = text1[:commonlength]
    text1 = text1[commonlength:]
    text2 = text2[commonlength:]

    # Trim off common suffix (speedup).
    commonlength = _diff_common_suffix(text1, text2)
    commonsuffix = text1[len(text1) - commonlength :]
    text1 = text1[: len(text1) - commonlength]
    text2 = text2[: len(text2) - commonlength]

    # Compute the diff on the middle block.
    diffs = _diff_compute(text1, text2)

    # Restore the prefix and suffix.
    if commonprefix:
        diffs.insert(0, [EQUAL, commonprefix])
    if commonsuffix:
        diffs.append([EQUAL, commonsuffix])
    _diff_cleanup_merge(diffs, fix_unicode)
    if cleanup:
        _diff_cleanup_semantic(diffs)
    return diffs


def _diff_compute(text1: str, text2: str) -> List[_Tuple]:
    """Find the differences between two texts with no common prefix or suffix."""
    if not text1:
        # Just add some text (speedup).
        return [[INSERT, text2]]

    if not text2:
        # Just delete some text (speedup).
        return [[DELETE, text1]]

    longtext = text1 if len(text1) > len(text2) else text2
    shorttext = text2 if len(text1) > len(text2) else text1
    i = longtext.find(shorttext)
    if i != -1:
        # Shorter text is inside the longer text (speedup).
        diffs = [
            [INSERT, longtext[:i]],
            [EQUAL, shorttext],
            [INSERT, longtext[i + len(shorttext) :]],
        ]
        # Swap insertions for deletions if diff is reversed.
        if len(text1) > len(text2):
            diffs[0][0] = diffs[2][0] = DELETE
        return diffs

    if len(shorttext) == 1:
        # Single character string.
        # After the previous speedup, the character can't be an equality.
        return [[DELETE, text1], [INSERT, text2]]

    # Check to see if the problem can be split in two.
    hm = _diff_half_match(text1, text2)
    if hm:
        # A half-match was found, sort out the return data.
        text1_a, text1_b, text2_a, text2_b, mid_common = hm
        # Send both pairs off for separate processing.
        diffs_a = _diff_main(text1_a, text2_a)
        diffs_b = _diff_main(text1_b, text2_b)
        # Merge the results.
        return diffs_a + [[EQUAL, mid_common]] + diffs_b

    return _diff_bisect(text1, text2)


def _diff_bisect(text1: str, text2: str) -> List[_Tuple]:
    """Find the 'middle snake' of a diff, split the problem in two and recurse.

    See Myers 1986 paper: An O(ND) Difference Algorithm and Its Variations.
    """
    # Cache the text lengths to prevent multiple calls.
    text1_length = len(text1)
    text2_length = len(text2)
    max_d = math.ceil((text1_length + text2_length) / 2)
    v_offset = max_d
    v_length = 2 * max_d
    # Setting all elements to -1 avoids mixing integers and undefined.
    v1 = [-1] * v_length
    v2 = [-1] * v_length
    v1[v_offset + 1] = 0
    v2[v_offset + 1] = 0
    delta = text1_length - text2_length
    # If the total number of characters is odd, then the front path will collide
    # with the reverse path.
    front = delta % 2 != 0
    # Offsets for start and end of k loop.
    # Prevents mapping of space beyond the grid.
    k1start = 0
    k1end = 0
    k2start = 0
    k2end = 0
    for d in range(max_d):
        # Walk the front path one step.
        for k1 in range(-d + k1start, d - k1end + 1, 2):
            k1_offset = v_offset + k1
            if k1 == -d or (k1 != d and v1[k1_offset - 1] < v1[k1_offset + 1]):
                x1 = v1[k1_offset + 1]
            else:
                x1 = v1[k1_offset - 1] + 1
            y1 = x1 - k1
            while (
                x1 < text1_length
                and y1 < text2_length
                and _char_at(text1, x1) == _char_at(text2, y1)
            ):
                x1 += 1
                y1 += 1
            v1[k1_offset] = x1
            if x1 > text1_length:
                # Ran off the right of the graph.
                k1end += 2
            elif y1 > text2_length:
                # Ran off the bottom of the graph.
                k1start += 2
            elif front:
                k2_offset = v_offset + delta - k1
                if 0 <= k2_offset < v_length and v2[k2_offset] != -1:
                    # Mirror x2 onto top-left coordinate system.
                    x2 = text1_length - v2[k2_offset]
                    if x1 >= x2:
                        # Overlap detected.
                        return _diff_bisect_split(text1, text2, x1, y1)

        # Walk the reverse path one step.
        for k2 in range(-d + k2start, d - k2end + 1, 2):
            k2_offset = v_offset + k2
            if k2 == -d or (k2 != d and v2[k2_offset - 1] < v2[k2_offset + 1]):
                x2 = v2[k2_offset + 1]
            else:
                x2 = v2[k2_offset - 1] + 1
            y2 = x2 - k2
            while (
                x2 < text1_length
                and y2 < text2_length
                and _char_at(text1, text1_length - x2 - 1) == _char_at(text2, text2_length - y2 - 1)
            ):
                x2 += 1
                y2 += 1
            v2[k2_offset] = x2
            if x2 > text1_length:
                # Ran off the left of the graph.
                k2end += 2
            elif y2 > text2_length:
                # Ran off the top of the graph.
                k2start += 2
            elif not front:
                k1_offset = v_offset + delta - k2
                if 0 <= k1_offset < v_length and v1[k1_offset] != -1:
                    x1 = v1[k1_offset]
                    y1 = v_offset + x1 - k1_offset
                    # Mirror x2 onto top-left coordinate system.
                    x2 = text1_length - x2
                    if x1 >= x2:
                        # Overlap detected.
                        return _diff_bisect_split(text1, text2, x1, y1)

    # Diff took too long and hit the deadline or
    # number of diffs equals number of characters, no commonality at all.
    return [[DELETE, text1], [INSERT, text2]]


def _diff_bisect_split(text1: str, text2: str, x: int, y: int) -> List[_Tuple]:
    """Given the location of the 'middle snake', split the diff in two parts and recurse."""
    text1a = text1[:x]
    text2a = text2[:y]
    text1b = text1[x:]
    text2b = text2[y:]

    # Compute both diffs serially.
    diffs = _diff_main(text1a, text2a)
    diffsb = _diff_main(text1b, text2b)

    return diffs + diffsb


def _diff_common_prefix(text1: str, text2: str) -> int:
    """The number of characters common to the start of each string."""
    # Quick check for common null cases.
    if not text1 or not text2 or _char_at(text1, 0) != _char_at(text2, 0):
        return 0
    # Binary search.
    # Performance analysis: http://neil.fraser.name/news/2007/10/09/
    pointermin = 0
    pointermax = min(len(text1), len(text2))
    pointermid = pointermax
    pointerstart = 0
    while pointermin < pointermid:
        if text1[pointerstart:pointermid] == text2[pointerstart:pointermid]:
            pointermin = pointermid
            pointerstart = pointermin
        else:
            pointermax = pointermid
        pointermid = math.floor((pointermax - pointermin) / 2 + pointermin)

    if _is_surrogate_pair_start(_char_code_at(text1, pointermid - 1)):
        pointermid -= 1

    return pointermid


def _diff_common_overlap(text1: str, text2: str) -> int:
    """The number of characters common to the end of text1 and the start of text2."""
    # Cache the text lengths to prevent multiple calls.
    text1_length = len(text1)
    text2_length = len(text2)
    # Eliminate the null case.
    if text1_length == 0 or text2_length == 0:
        return 0
    # Truncate the longer string.
    if text1_length > text2_length:
        text1 = text1[text1_length - text2_length :]
    elif text1_length < text2_length:
        text2 = text2[:text1_length]
    text_length = min(text1_length, text2_length)
    # Quick check for the worst case.
    if text1 == text2:
        return text_length

    # Start by looking for a single character match
    # and increase length until no match is found.
    # Performance analysis: http://neil.fraser.name/news/2010/11/04/
    best = 0
    length = 1
    while True:
        pattern = text1[text_length - length :]
        found = text2.find(pattern)
        if found == -1:
            return best
        length += found
        if found == 0 or text1[text_length - length :] == text2[:length]:
            best = length
            length += 1


def _diff_common_suffix(text1: str, text2: str) -> int:
    """The number of characters common to the end of each string."""
    # Quick check for common null cases.
    if not text1 or not text2 or text1[-1:] != text2[-1:]:
        return 0
    # Binary search.
    # Performance analysis: http://neil.fraser.name/news/2007/10/09/
    pointermin = 0
    pointermax = min(len(text1), len(text2))
    pointermid = pointermax
    pointerend = 0
    while pointermin < pointermid:
        left = text1[len(text1) - pointermid : len(text1) - pointerend]
        right = text2[len(text2) - pointermid : len(text2) - pointerend]
        if left == right:
            pointermin = pointermid
            pointerend = pointermin
        else:
            pointermax = pointermid
        pointermid = math.floor((pointermax - pointermin) / 2 + pointermin)

    if _is_surrogate_pair_end(_char_code_at(text1, len(text1) - pointermid)):
        pointermid -= 1

    return pointermid


def _diff_half_match(text1: str, text2: str) -> Optional[List[str]]:
    """Do the two texts share a substring at least half the length of the longer text?

    This speedup can produce non-minimal diffs. Returns a five element list containing the
    prefix of text1, the suffix of text1, the prefix of text2, the suffix of text2 and the
    common middle, or ``None`` if there was no match.
    """
    longtext = text1 if len(text1) > len(text2) else text2
    shorttext = text2 if len(text1) > len(text2) else text1
    if len(longtext) < 4 or len(shorttext) * 2 < len(longtext):
        return None  # Pointless.

    def diff_half_match_i(longtext: str, shorttext: str, i: int) -> Optional[List[str]]:
        """Does a substring of shorttext exist within longtext such that the substring is at
        least half the length of longtext?
        """
        # Start with a 1/4 length substring at position i as a seed.
        seed = longtext[i : i + math.floor(len(longtext) / 4)]
        j = -1
        best_common = ''
        best_longtext_a = best_longtext_b = best_shorttext_a = best_shorttext_b = ''
        while True:
            j = shorttext.find(seed, j + 1)
            if j == -1:
                break
            prefix_length = _diff_common_prefix(longtext[i:], shorttext[j:])
            suffix_length = _diff_common_suffix(longtext[:i], shorttext[:j])
            if len(best_common) < suffix_length + prefix_length:
                best_common = shorttext[j - suffix_length : j] + shorttext[j : j + prefix_length]
                best_longtext_a = longtext[: i - suffix_length]
                best_longtext_b = longtext[i + prefix_length :]
                best_shorttext_a = shorttext[: j - suffix_length]
                best_shorttext_b = shorttext[j + prefix_length :]
        if len(best_common) * 2 >= len(longtext):
            return [
                best_longtext_a,
                best_longtext_b,
                best_shorttext_a,
                best_shorttext_b,
                best_common,
            ]
        return None

    # First check if the second quarter is the seed for a half-match.
    hm1 = diff_half_match_i(longtext, shorttext, math.ceil(len(longtext) / 4))
    # Check again based on the third quarter.
    hm2 = diff_half_match_i(longtext, shorttext, math.ceil(len(longtext) / 2))
    if not hm1 and not hm2:
        return None
    elif not hm2:
        hm = hm1
    elif not hm1:
        hm = hm2
    else:
        # Both matched. Select the longest.
        hm = hm1 if len(hm1[4]) > len(hm2[4]) else hm2
    assert hm is not None

    # A half-match was found, sort out the return data.
    if len(text1) > len(text2):
        text1_a, text1_b, text2_a, text2_b = hm[0], hm[1], hm[2], hm[3]
    else:
        text2_a, text2_b, text1_a, text1_b = hm[0], hm[1], hm[2], hm[3]
    mid_common = hm[4]
    return [text1_a, text1_b, text2_a, text2_b, mid_common]


def _diff_cleanup_semantic(diffs: List[_Tuple]) -> None:
    """Reduce the number of edits by eliminating semantically trivial equalities."""
    changes = False
    # Stack of indices where equalities are found. Keyed by position rather than a list
    # because `equalities_length` can go negative, and the JavaScript original then keeps
    # reading and writing at those negative indices.
    equalities: dict[int, int] = {}
    equalities_length = 0
    last_equality: Optional[str] = None
    # Always equal to diffs[equalities[equalities_length - 1]][1]
    pointer = 0  # Index of current position.
    # Number of characters that changed prior to the equality.
    length_insertions1 = 0
    length_deletions1 = 0
    # Number of characters that changed after the equality.
    length_insertions2 = 0
    length_deletions2 = 0
    while pointer < len(diffs):
        if diffs[pointer][0] == EQUAL:
            # Equality found.
            equalities[equalities_length] = pointer
            equalities_length += 1
            length_insertions1 = length_insertions2
            length_deletions1 = length_deletions2
            length_insertions2 = 0
            length_deletions2 = 0
            last_equality = diffs[pointer][1]
        else:
            # An insertion or deletion.
            if diffs[pointer][0] == INSERT:
                length_insertions2 += len(diffs[pointer][1])
            else:
                length_deletions2 += len(diffs[pointer][1])
            # Eliminate an equality that is smaller or equal to the edits on both
            # sides of it.
            if (
                last_equality
                and len(last_equality) <= max(length_insertions1, length_deletions1)
                and len(last_equality) <= max(length_insertions2, length_deletions2)
            ):
                # Duplicate record.
                diffs.insert(equalities[equalities_length - 1], [DELETE, last_equality])
                # Change second copy to insert.
                diffs[equalities[equalities_length - 1] + 1][0] = INSERT
                # Throw away the equality we just deleted.
                equalities_length -= 1
                # Throw away the previous equality (it needs to be reevaluated).
                equalities_length -= 1
                pointer = equalities[equalities_length - 1] if equalities_length > 0 else -1
                length_insertions1 = 0  # Reset the counters.
                length_deletions1 = 0
                length_insertions2 = 0
                length_deletions2 = 0
                last_equality = None
                changes = True
        pointer += 1

    # Normalize the diff.
    if changes:
        _diff_cleanup_merge(diffs)
    _diff_cleanup_semantic_lossless(diffs)

    # Find any overlaps between deletions and insertions.
    # e.g: <del>abcxxx</del><ins>xxxdef</ins>
    #   -> <del>abc</del>xxx<ins>def</ins>
    # e.g: <del>xxxabc</del><ins>defxxx</ins>
    #   -> <ins>def</ins>xxx<del>abc</del>
    # Only extract an overlap if it is as big as the edit ahead or behind it.
    pointer = 1
    while pointer < len(diffs):
        if diffs[pointer - 1][0] == DELETE and diffs[pointer][0] == INSERT:
            deletion = diffs[pointer - 1][1]
            insertion = diffs[pointer][1]
            overlap_length1 = _diff_common_overlap(deletion, insertion)
            overlap_length2 = _diff_common_overlap(insertion, deletion)
            if overlap_length1 >= overlap_length2:
                if overlap_length1 >= len(deletion) / 2 or overlap_length1 >= len(insertion) / 2:
                    # Overlap found. Insert an equality and trim the surrounding edits.
                    diffs.insert(pointer, [EQUAL, insertion[:overlap_length1]])
                    diffs[pointer - 1][1] = deletion[: len(deletion) - overlap_length1]
                    diffs[pointer + 1][1] = insertion[overlap_length1:]
                    pointer += 1
            else:
                if overlap_length2 >= len(deletion) / 2 or overlap_length2 >= len(insertion) / 2:
                    # Reverse overlap found.
                    # Insert an equality and swap and trim the surrounding edits.
                    diffs.insert(pointer, [EQUAL, deletion[:overlap_length2]])
                    diffs[pointer - 1][0] = INSERT
                    diffs[pointer - 1][1] = insertion[: len(insertion) - overlap_length2]
                    diffs[pointer + 1][0] = DELETE
                    diffs[pointer + 1][1] = deletion[overlap_length2:]
                    pointer += 1
            pointer += 1
        pointer += 1


_NON_ALPHA_NUMERIC_RE = re.compile(r'[^a-zA-Z0-9]')
_WHITESPACE_RE = re.compile(r'\s')
_LINEBREAK_RE = re.compile(r'[\r\n]')
_BLANKLINE_END_RE = re.compile(r'\n\r?\n$')
_BLANKLINE_START_RE = re.compile(r'^\r?\n\r?\n')


def _diff_cleanup_semantic_lossless(diffs: List[_Tuple]) -> None:
    """Shift single edits surrounded by equalities sideways to align to a word boundary.

    e.g: The c<ins>at c</ins>ame. -> The <ins>cat </ins>came.
    """

    def cleanup_semantic_score(one: str, two: str) -> int:
        """Score whether the internal boundary falls on logical boundaries.

        Scores range from 6 (best) to 0 (worst).
        """
        if not one or not two:
            # Edges are the best.
            return 6

        # Each port of this function behaves slightly differently due to
        # subtle differences in each language's definition of things like
        # 'whitespace'. Since this function's purpose is largely cosmetic,
        # the choice has been made to use each language's native features
        # rather than force total conformity.
        char1 = one[len(one) - 1]
        char2 = two[0]
        non_alpha_numeric1 = _NON_ALPHA_NUMERIC_RE.search(char1)
        non_alpha_numeric2 = _NON_ALPHA_NUMERIC_RE.search(char2)
        whitespace1 = non_alpha_numeric1 and _WHITESPACE_RE.search(char1)
        whitespace2 = non_alpha_numeric2 and _WHITESPACE_RE.search(char2)
        line_break1 = whitespace1 and _LINEBREAK_RE.search(char1)
        line_break2 = whitespace2 and _LINEBREAK_RE.search(char2)
        blank_line1 = line_break1 and _BLANKLINE_END_RE.search(one)
        blank_line2 = line_break2 and _BLANKLINE_START_RE.search(two)

        if blank_line1 or blank_line2:
            # Five points for blank lines.
            return 5
        elif line_break1 or line_break2:
            # Four points for line breaks.
            return 4
        elif non_alpha_numeric1 and not whitespace1 and whitespace2:
            # Three points for end of sentences.
            return 3
        elif whitespace1 or whitespace2:
            # Two points for whitespace.
            return 2
        elif non_alpha_numeric1 or non_alpha_numeric2:
            # One point for non-alphanumeric.
            return 1
        return 0

    pointer = 1
    # Intentionally ignore the first and last element (don't need checking).
    while pointer < len(diffs) - 1:
        if diffs[pointer - 1][0] == EQUAL and diffs[pointer + 1][0] == EQUAL:
            # This is a single edit surrounded by equalities.
            equality1 = diffs[pointer - 1][1]
            edit = diffs[pointer][1]
            equality2 = diffs[pointer + 1][1]

            # First, shift the edit as far left as possible.
            common_offset = _diff_common_suffix(equality1, edit)
            if common_offset:
                common_string = edit[len(edit) - common_offset :]
                equality1 = equality1[: len(equality1) - common_offset]
                edit = common_string + edit[: len(edit) - common_offset]
                equality2 = common_string + equality2

            # Second, step character by character right, looking for the best fit.
            best_equality1 = equality1
            best_edit = edit
            best_equality2 = equality2
            best_score = cleanup_semantic_score(equality1, edit) + cleanup_semantic_score(
                edit, equality2
            )
            while _char_at(edit, 0) == _char_at(equality2, 0):
                equality1 += _char_at(edit, 0)
                edit = edit[1:] + _char_at(equality2, 0)
                equality2 = equality2[1:]
                score = cleanup_semantic_score(equality1, edit) + cleanup_semantic_score(
                    edit, equality2
                )
                # The >= encourages trailing rather than leading whitespace on edits.
                if score >= best_score:
                    best_score = score
                    best_equality1 = equality1
                    best_edit = edit
                    best_equality2 = equality2

            if diffs[pointer - 1][1] != best_equality1:
                # We have an improvement, save it back to the diff.
                if best_equality1:
                    diffs[pointer - 1][1] = best_equality1
                else:
                    del diffs[pointer - 1]
                    pointer -= 1
                diffs[pointer][1] = best_edit
                if best_equality2:
                    diffs[pointer + 1][1] = best_equality2
                else:
                    del diffs[pointer + 1]
                    pointer -= 1
        pointer += 1


def _diff_cleanup_merge(diffs: List[_Tuple], fix_unicode: bool = False) -> None:
    """Reorder and merge like edit sections, and merge equalities.

    Any edit section can move as long as it doesn't cross an equality.
    """
    diffs.append([EQUAL, ''])  # Add a dummy entry at the end.
    pointer = 0
    count_delete = 0
    count_insert = 0
    text_delete = ''
    text_insert = ''
    while pointer < len(diffs):
        if pointer < len(diffs) - 1 and not diffs[pointer][1]:
            del diffs[pointer]
            continue
        if diffs[pointer][0] == INSERT:
            count_insert += 1
            text_insert += diffs[pointer][1]
            pointer += 1
        elif diffs[pointer][0] == DELETE:
            count_delete += 1
            text_delete += diffs[pointer][1]
            pointer += 1
        else:  # EQUAL
            previous_equality = pointer - count_insert - count_delete - 1
            if fix_unicode:
                # prevent splitting of unicode surrogate pairs. when fix_unicode is true,
                # we assume that the old and new text in the diff are complete and correct
                # unicode-encoded strings, but the tuple boundaries may fall between
                # surrogate pairs. we fix this by shaving off stray surrogates from the end
                # of the previous equality and the beginning of this equality. this may
                # create empty equalities or a common prefix or suffix. for example, if AB
                # and AC are emojis, `[[0, 'A'], [-1, 'BA'], [0, 'C']]` would turn into
                # deleting 'ABAC' and inserting 'AC', and then the common suffix 'AC' will
                # be eliminated. in this particular case, both equalities go away, we absorb
                # any previous inequalities, and we keep scanning for the next equality
                # before rewriting the tuples.
                if previous_equality >= 0 and _ends_with_pair_start(diffs[previous_equality][1]):
                    stray = diffs[previous_equality][1][-1:]
                    diffs[previous_equality][1] = diffs[previous_equality][1][:-1]
                    text_delete = stray + text_delete
                    text_insert = stray + text_insert
                    if not diffs[previous_equality][1]:
                        # emptied out previous equality, so delete it and include previous
                        # delete/insert
                        del diffs[previous_equality]
                        pointer -= 1
                        k = previous_equality - 1
                        if _at(diffs, k) is not None and diffs[k][0] == INSERT:
                            count_insert += 1
                            text_insert = diffs[k][1] + text_insert
                            k -= 1
                        if _at(diffs, k) is not None and diffs[k][0] == DELETE:
                            count_delete += 1
                            text_delete = diffs[k][1] + text_delete
                            k -= 1
                        previous_equality = k
                if _starts_with_pair_end(diffs[pointer][1]):
                    stray = _char_at(diffs[pointer][1], 0)
                    diffs[pointer][1] = diffs[pointer][1][1:]
                    text_delete += stray
                    text_insert += stray
            if pointer < len(diffs) - 1 and not diffs[pointer][1]:
                # for empty equality not at end, wait for next equality
                del diffs[pointer]
                continue
            if len(text_delete) > 0 or len(text_insert) > 0:
                # note that _diff_common_prefix and _diff_common_suffix are unicode-aware
                if len(text_delete) > 0 and len(text_insert) > 0:
                    # Factor out any common prefixes.
                    commonlength = _diff_common_prefix(text_insert, text_delete)
                    if commonlength != 0:
                        if previous_equality >= 0:
                            diffs[previous_equality][1] += text_insert[:commonlength]
                        else:
                            diffs.insert(0, [EQUAL, text_insert[:commonlength]])
                            pointer += 1
                        text_insert = text_insert[commonlength:]
                        text_delete = text_delete[commonlength:]
                    # Factor out any common suffixes.
                    commonlength = _diff_common_suffix(text_insert, text_delete)
                    if commonlength != 0:
                        diffs[pointer][1] = (
                            text_insert[len(text_insert) - commonlength :] + diffs[pointer][1]
                        )
                        text_insert = text_insert[: len(text_insert) - commonlength]
                        text_delete = text_delete[: len(text_delete) - commonlength]
                # Delete the offending records and add the merged ones.
                n = count_insert + count_delete
                if len(text_delete) == 0 and len(text_insert) == 0:
                    del diffs[pointer - n : pointer]
                    pointer = pointer - n
                elif len(text_delete) == 0:
                    diffs[pointer - n : pointer] = [[INSERT, text_insert]]
                    pointer = pointer - n + 1
                elif len(text_insert) == 0:
                    diffs[pointer - n : pointer] = [[DELETE, text_delete]]
                    pointer = pointer - n + 1
                else:
                    diffs[pointer - n : pointer] = [
                        [DELETE, text_delete],
                        [INSERT, text_insert],
                    ]
                    pointer = pointer - n + 2
            if pointer != 0 and diffs[pointer - 1][0] == EQUAL:
                # Merge this equality with the previous one.
                diffs[pointer - 1][1] += diffs[pointer][1]
                del diffs[pointer]
            else:
                pointer += 1
            count_insert = 0
            count_delete = 0
            text_delete = ''
            text_insert = ''
    if diffs[len(diffs) - 1][1] == '':
        diffs.pop()  # Remove the dummy entry at the end.

    # Second pass: look for single edits surrounded on both sides by equalities
    # which can be shifted sideways to eliminate an equality.
    # e.g: A<ins>BA</ins>C -> <ins>AB</ins>AC
    changes = False
    pointer = 1
    # Intentionally ignore the first and last element (don't need checking).
    while pointer < len(diffs) - 1:
        if diffs[pointer - 1][0] == EQUAL and diffs[pointer + 1][0] == EQUAL:
            # This is a single edit surrounded by equalities.
            if (
                diffs[pointer][1][len(diffs[pointer][1]) - len(diffs[pointer - 1][1]) :]
                == diffs[pointer - 1][1]
            ):
                # Shift the edit over the previous equality.
                diffs[pointer][1] = (
                    diffs[pointer - 1][1]
                    + diffs[pointer][1][: len(diffs[pointer][1]) - len(diffs[pointer - 1][1])]
                )
                diffs[pointer + 1][1] = diffs[pointer - 1][1] + diffs[pointer + 1][1]
                del diffs[pointer - 1]
                changes = True
            elif diffs[pointer][1][: len(diffs[pointer + 1][1])] == diffs[pointer + 1][1]:
                # Shift the edit over the next equality.
                diffs[pointer - 1][1] += diffs[pointer + 1][1]
                diffs[pointer][1] = (
                    diffs[pointer][1][len(diffs[pointer + 1][1]) :] + diffs[pointer + 1][1]
                )
                del diffs[pointer + 1]
                changes = True
        pointer += 1
    # If shifts were made, the diff needs reordering and another shift sweep.
    if changes:
        _diff_cleanup_merge(diffs, fix_unicode)


def _at(items: List[_Tuple], index: int) -> Optional[_Tuple]:
    """``items[index]`` in JavaScript: out of range is ``undefined``, and never wraps."""
    if 0 <= index < len(items):
        return items[index]
    return None


def _is_surrogate_pair_start(char_code: int) -> bool:
    return 0xD800 <= char_code <= 0xDBFF


def _is_surrogate_pair_end(char_code: int) -> bool:
    return 0xDC00 <= char_code <= 0xDFFF


def _starts_with_pair_end(text: str) -> bool:
    return _is_surrogate_pair_end(_char_code_at(text, 0))


def _ends_with_pair_start(text: str) -> bool:
    return _is_surrogate_pair_start(_char_code_at(text, len(text) - 1))


def _remove_empty_tuples(tuples: List[_Tuple]) -> List[_Tuple]:
    return [tuple_ for tuple_ in tuples if len(tuple_[1]) > 0]


def _make_edit_splice(
    before: str, old_middle: str, new_middle: str, after: str
) -> Optional[List[_Tuple]]:
    if _ends_with_pair_start(before) or _starts_with_pair_end(after):
        return None
    return _remove_empty_tuples(
        [
            [EQUAL, before],
            [DELETE, old_middle],
            [INSERT, new_middle],
            [EQUAL, after],
        ]
    )


_BREAK = object()
"""Leaving a labelled block, as opposed to returning from the function."""


def _find_cursor_edit_diff(
    old_text: str, new_text: str, cursor_pos: CursorPos
) -> Optional[List[_Tuple]]:
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
