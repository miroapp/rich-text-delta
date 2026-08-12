# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import math

from rich_text_delta import Delta, OpIterator

delta = (
    Delta()
    .insert('Hello', {'bold': True})
    .retain(3)
    .insert({'embed': 2}, {'src': 'http://quilljs.com/'})
    .delete(4)
)


def test_has_next_true() -> None:
    iterator = OpIterator(delta.ops)
    assert iterator.has_next() is True


def test_has_next_false() -> None:
    iterator = OpIterator([])
    assert iterator.has_next() is False


def test_peek_length_offset_is_zero() -> None:
    iterator = OpIterator(delta.ops)
    assert iterator.peek_length() == 5
    iterator.next()
    assert iterator.peek_length() == 3
    iterator.next()
    assert iterator.peek_length() == 1
    iterator.next()
    assert iterator.peek_length() == 4


def test_peek_length_offset_greater_than_zero() -> None:
    iterator = OpIterator(delta.ops)
    iterator.next(2)
    assert iterator.peek_length() == 5 - 2


def test_peek_length_no_ops_left() -> None:
    iterator = OpIterator([])
    assert iterator.peek_length() == math.inf


def test_peek_type() -> None:
    iterator = OpIterator(delta.ops)
    assert iterator.peek_type() == 'insert'
    iterator.next()
    assert iterator.peek_type() == 'retain'
    iterator.next()
    assert iterator.peek_type() == 'insert'
    iterator.next()
    assert iterator.peek_type() == 'delete'
    iterator.next()
    assert iterator.peek_type() == 'retain'


def test_next() -> None:
    iterator = OpIterator(delta.ops)
    for op in delta.ops:
        assert iterator.next() == op
    assert iterator.next() == {'retain': math.inf}
    assert iterator.next(4) == {'retain': math.inf}
    assert iterator.next() == {'retain': math.inf}


def test_next_length() -> None:
    iterator = OpIterator(delta.ops)
    assert iterator.next(2) == {'insert': 'He', 'attributes': {'bold': True}}
    assert iterator.next(10) == {'insert': 'llo', 'attributes': {'bold': True}}
    assert iterator.next(1) == {'retain': 1}
    assert iterator.next(2) == {'retain': 2}


def test_rest() -> None:
    iterator = OpIterator(delta.ops)
    iterator.next(2)
    assert iterator.rest() == [
        {'insert': 'llo', 'attributes': {'bold': True}},
        {'retain': 3},
        {'insert': {'embed': 2}, 'attributes': {'src': 'http://quilljs.com/'}},
        {'delete': 4},
    ]
    iterator.next(3)
    assert iterator.rest() == [
        {'retain': 3},
        {'insert': {'embed': 2}, 'attributes': {'src': 'http://quilljs.com/'}},
        {'delete': 4},
    ]
    iterator.next(3)
    iterator.next(2)
    iterator.next(4)
    assert iterator.rest() == []
