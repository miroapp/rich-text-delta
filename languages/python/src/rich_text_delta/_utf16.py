# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""Text measured and indexed in UTF-16 code units, as JavaScript measures it.

The delta format addresses positions in UTF-16 code units, so an astral character — one
outside the Basic Multilingual Plane, such as an emoji — spans two of them. Python's ``str``
is a sequence of code points, where the same character spans one, hence this module: every
length and every offset in the package is a code-unit count, obtained here.

Insert text is an ordinary ``str`` in canonical form: **maximally composed, lone surrogates
tolerated**. Astral characters are stored composed, so ``op['insert']`` stays readable, while
a split landing inside a surrogate pair yields a lone surrogate, exactly as the reference
implementation produces. That form is what :func:`json.loads` yields — it recombines a pair of
escapes into one character and leaves an unpaired escape alone — so a wire round-trip is the
identity.

Encoding to ``utf-16-le`` is how a ``str`` becomes a sequence of code units. ``surrogatepass``
is required throughout: a lone surrogate is data here, not an error. Note that a composed
astral character and its decomposed surrogate pair encode to the *same* bytes, so measuring
and slicing are insensitive to which form a string happens to hold.
"""

from __future__ import annotations

import re

_ENCODING = 'utf-16-le'
_ERRORS = 'surrogatepass'

_HIGH_MIN, _HIGH_MAX = '\ud800', '\udbff'
_LOW_MIN, _LOW_MAX = '\udc00', '\udfff'

_ASTRAL = re.compile('[^\\x00-\\uffff]')
"""Every character that needs a surrogate pair, i.e. every one outside the BMP."""


def units(text: str) -> bytes:
    """``text`` as raw UTF-16 code units, two bytes each."""
    return text.encode(_ENCODING, _ERRORS)


def decode(data: bytes) -> str:
    """Code units back to canonical ``str``: pairs recombine, lone surrogates survive."""
    return data.decode(_ENCODING, _ERRORS)


def length(text: str) -> int:
    """How many code units ``text`` occupies. ``text.length`` in JavaScript."""
    # `isascii()` reads a cached flag, so the common case costs no encode.
    return len(text) if text.isascii() else len(units(text)) // 2


def slice_units(data: bytes, start: int, end: int) -> str:
    """``data[start:end]`` in code units, decoded back to canonical ``str``.

    ``data`` comes from :func:`units`, so this is ``text.slice(start, end)`` in JavaScript. A
    boundary falling inside a surrogate pair splits it, yielding a lone surrogate at that end
    — well-formed UTF-16, though not valid Unicode.
    """
    return decode(data[2 * start : 2 * end])


def recompose(text: str) -> str:
    """Canonical form: an adjacent surrogate pair becomes the one character it encodes."""
    return text if text.isascii() else decode(units(text))


def decompose(text: str) -> str:
    """One character per code unit: every astral character becomes its surrogate pair.

    The inverse of :func:`recompose`, and the form in which ``str`` operations — ``len``,
    indexing, ``find`` — coincide with their JavaScript counterparts. Used to hand text to
    ``_fast_diff``, which is a port of a library written against JavaScript strings.
    """
    return text if text.isascii() else _ASTRAL.sub(_expand, text)


def _expand(match: re.Match[str]) -> str:
    code = ord(match.group()) - 0x10000
    return chr(0xD800 + (code >> 10)) + chr(0xDC00 + (code & 0x3FF))


def join(left: str, right: str) -> str:
    """``left + right`` in JavaScript: a pair formed at the seam becomes one character.

    Concatenating two halves of a split surrogate pair has to put the pair back together, or
    the result would hold two code points where the reference holds one character, and would
    no longer be in canonical form. Checking just the seam keeps this O(1), which matters
    because ``Delta.push`` merges inserts in a loop.
    """
    if left and right and _HIGH_MIN <= left[-1] <= _HIGH_MAX and _LOW_MIN <= right[0] <= _LOW_MAX:
        code = 0x10000 + ((ord(left[-1]) - 0xD800) << 10) + (ord(right[0]) - 0xDC00)
        return left[:-1] + chr(code) + right[1:]
    return left + right


def find_units(data: bytes, needle: bytes, start: int = 0) -> int:
    """``data.indexOf(needle, start)`` in JavaScript: offsets and result in code units.

    Both arguments come from :func:`units`.
    """
    position = 2 * max(start, 0)  # JavaScript clamps a negative start rather than wrapping
    while True:
        position = data.find(needle, position)
        if position < 0:
            return -1
        # A match starting at an odd byte spans two code units without being either, so it
        # is not a match at all: skip past it rather than reporting a bogus offset.
        if position % 2 == 0:
            return position // 2
        position += 1
