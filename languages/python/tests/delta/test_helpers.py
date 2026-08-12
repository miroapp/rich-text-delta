# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import json
from typing import Any, Optional
from unittest.mock import Mock, call

from rich_text_delta import Delta, Op


class TestConcat:
    def test_empty_delta(self) -> None:
        delta = Delta().insert('Test')
        concat = Delta()
        expected = Delta().insert('Test')
        assert delta.concat(concat) == expected

    def test_unmergeable(self) -> None:
        delta = Delta().insert('Test')
        original = Delta(json.loads(json.dumps({'ops': delta.ops})))
        concat = Delta().insert('!', {'bold': True})
        expected = Delta().insert('Test').insert('!', {'bold': True})
        assert delta.concat(concat) == expected
        assert delta == original

    def test_mergeable(self) -> None:
        delta = Delta().insert('Test', {'bold': True})
        original = Delta(json.loads(json.dumps({'ops': delta.ops})))
        concat = Delta().insert('!', {'bold': True}).insert('\n')
        expected = Delta().insert('Test!', {'bold': True}).insert('\n')
        assert delta.concat(concat) == expected
        assert delta == original


class TestChop:
    def test_retain(self) -> None:
        delta = Delta().insert('Test').retain(4)
        expected = Delta().insert('Test')
        assert delta.chop() == expected

    def test_insert(self) -> None:
        delta = Delta().insert('Test')
        expected = Delta().insert('Test')
        assert delta.chop() == expected

    def test_formatted_retain(self) -> None:
        delta = Delta().insert('Test').retain(4, {'bold': True})
        expected = Delta().insert('Test').retain(4, {'bold': True})
        assert delta.chop() == expected


class TestEachLine:
    def test_expected(self) -> None:
        spy = Mock(return_value=None)
        delta = (
            Delta()
            .insert('Hello\n\n')
            .insert('World', {'bold': True})
            .insert({'image': 'octocat.png'})
            .insert('\n', {'align': 'right'})
            .insert('!')
        )
        delta.each_line(spy)
        assert spy.call_count == 4
        assert spy.call_args_list[0] == call(Delta().insert('Hello'), {}, 0)
        assert spy.call_args_list[1] == call(Delta(), {}, 1)
        assert spy.call_args_list[2] == call(
            Delta().insert('World', {'bold': True}).insert({'image': 'octocat.png'}),
            {'align': 'right'},
            2,
        )
        assert spy.call_args_list[3] == call(Delta().insert('!'), {}, 3)

    def test_trailing_newline(self) -> None:
        spy = Mock(return_value=None)
        delta = Delta().insert('Hello\nWorld!\n')
        delta.each_line(spy)
        assert spy.call_count == 2
        assert spy.call_args_list[0] == call(Delta().insert('Hello'), {}, 0)
        assert spy.call_args_list[1] == call(Delta().insert('World!'), {}, 1)

    def test_non_document(self) -> None:
        spy = Mock(return_value=None)
        delta = Delta().retain(1).delete(2)
        delta.each_line(spy)
        assert spy.call_count == 0

    def test_early_return(self) -> None:
        delta = Delta().insert('Hello\nNew\nWorld!')
        count = 0

        def each(*_args: Any) -> Optional[bool]:
            nonlocal count
            if count == 1:
                return False
            count += 1
            return None

        spy = Mock(side_effect=each)
        delta.each_line(spy)
        assert spy.call_count == 2


class TestIteration:
    delta = Delta().insert('Hello').insert({'image': True}).insert('World!')

    def test_filter(self) -> None:
        arr = self.delta.filter(lambda op, _index: isinstance(op.get('insert'), str))
        assert len(arr) == 2

    def test_for_each(self) -> None:
        spy = Mock(return_value=None)
        self.delta.for_each(spy)
        assert spy.call_count == 3

    def test_map(self) -> None:
        def to_text(op: Op, _index: int) -> str:
            insert = op.get('insert')
            return insert if isinstance(insert, str) else ''

        arr = self.delta.map(to_text)
        assert arr == ['Hello', '', 'World!']

    def test_partition(self) -> None:
        arr = self.delta.partition(lambda op: isinstance(op.get('insert'), str))
        passed, failed = arr[0], arr[1]
        assert passed == [self.delta.ops[0], self.delta.ops[2]]
        assert failed == [self.delta.ops[1]]


class TestLength:
    def test_document(self) -> None:
        delta = Delta().insert('AB', {'bold': True}).insert({'embed': 1})
        assert delta.length() == 3

    def test_mixed(self) -> None:
        delta = (
            Delta()
            .insert('AB', {'bold': True})
            .insert({'embed': 1})
            .retain(2, {'bold': None})
            .delete(1)
        )
        assert delta.length() == 6


class TestChangeLength:
    def test_mixed(self) -> None:
        delta = Delta().insert('AB', {'bold': True}).retain(2, {'bold': None}).delete(1)
        assert delta.change_length() == 1


class TestSlice:
    def test_start(self) -> None:
        sliced = Delta().retain(2).insert('A').slice(2)
        expected = Delta().insert('A')
        assert sliced == expected

    def test_start_and_end_chop(self) -> None:
        sliced = Delta().insert('0123456789').slice(2, 7)
        expected = Delta().insert('23456')
        assert sliced == expected

    def test_start_and_end_multiple_chop(self) -> None:
        sliced = Delta().insert('0123', {'bold': True}).insert('4567').slice(3, 5)
        expected = Delta().insert('3', {'bold': True}).insert('4')
        assert sliced == expected

    def test_start_and_end(self) -> None:
        sliced = Delta().retain(2).insert('A', {'bold': True}).insert('B').slice(2, 3)
        expected = Delta().insert('A', {'bold': True})
        assert sliced == expected

    def test_no_params(self) -> None:
        delta = Delta().retain(2).insert('A', {'bold': True}).insert('B')
        sliced = delta.slice()
        assert sliced == delta

    def test_split_ops(self) -> None:
        sliced = Delta().insert('AB', {'bold': True}).insert('C').slice(1, 2)
        expected = Delta().insert('B', {'bold': True})
        assert sliced == expected

    def test_split_ops_multiple_times(self) -> None:
        sliced = Delta().insert('ABC', {'bold': True}).insert('D').slice(1, 2)
        expected = Delta().insert('B', {'bold': True})
        assert sliced == expected
