# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import pytest

from rich_text_delta import Delta
from rich_text_delta._js import UNDEFINED


def test_insert() -> None:
    a = Delta().insert('A')
    b = Delta().insert('AB')
    expected = Delta().retain(1).insert('B')
    assert a.diff(b) == expected


def test_delete() -> None:
    a = Delta().insert('AB')
    b = Delta().insert('A')
    expected = Delta().retain(1).delete(1)
    assert a.diff(b) == expected


def test_retain() -> None:
    a = Delta().insert('A')
    b = Delta().insert('A')
    expected = Delta()
    assert a.diff(b) == expected


def test_format() -> None:
    a = Delta().insert('A')
    b = Delta().insert('A', {'bold': True})
    expected = Delta().retain(1, {'bold': True})
    assert a.diff(b) == expected


def test_object_attributes() -> None:
    a = Delta().insert('A', {'font': {'family': 'Helvetica', 'size': '15px'}})
    b = Delta().insert('A', {'font': {'family': 'Helvetica', 'size': '15px'}})
    expected = Delta()
    assert a.diff(b) == expected


def test_embed_integer_match() -> None:
    a = Delta().insert({'embed': 1})
    b = Delta().insert({'embed': 1})
    expected = Delta()
    assert a.diff(b) == expected


def test_embed_integer_mismatch() -> None:
    a = Delta().insert({'embed': 1})
    b = Delta().insert({'embed': 2})
    expected = Delta().delete(1).insert({'embed': 2})
    assert a.diff(b) == expected


def test_embed_object_match() -> None:
    a = Delta().insert({'image': 'http://quilljs.com'})
    b = Delta().insert({'image': 'http://quilljs.com'})
    expected = Delta()
    assert a.diff(b) == expected


def test_embed_object_mismatch() -> None:
    a = Delta().insert({'image': 'http://quilljs.com', 'alt': 'Overwrite'})
    b = Delta().insert({'image': 'http://quilljs.com'})
    expected = Delta().insert({'image': 'http://quilljs.com'}).delete(1)
    assert a.diff(b) == expected


def test_embed_object_change() -> None:
    embed = {'image': 'http://quilljs.com'}
    a = Delta().insert(embed)
    embed['image'] = 'http://github.com'
    b = Delta().insert(embed)
    expected = Delta().insert({'image': 'http://github.com'}).delete(1)
    assert a.diff(b) == expected


def test_embed_false_positive() -> None:
    a = Delta().insert({'embed': 1})
    b = Delta().insert(chr(0))  # Placeholder char for embed in diff()
    expected = Delta().insert(chr(0)).delete(1)
    assert a.diff(b) == expected


def test_error_on_non_documents() -> None:
    a = Delta().insert('A')
    b = Delta().retain(1).insert('B')
    with pytest.raises(ValueError):
        a.diff(b)
    with pytest.raises(ValueError):
        b.diff(a)


def test_inconvenient_indexes() -> None:
    a = Delta().insert('12', {'bold': True}).insert('34', {'italic': True})
    b = Delta().insert('123', {'color': 'red'})
    expected = (
        Delta()
        .retain(2, {'bold': None, 'color': 'red'})
        .retain(1, {'italic': None, 'color': 'red'})
        .delete(1)
    )
    assert a.diff(b) == expected


def test_combination() -> None:
    a = Delta().insert('Bad', {'color': 'red'}).insert('cat', {'color': 'blue'})
    b = Delta().insert('Good', {'bold': True}).insert('dog', {'italic': True})
    expected = Delta().insert('Good', {'bold': True}).insert('dog', {'italic': True}).delete(6)
    assert a.diff(b) == expected


def test_same_document() -> None:
    a = Delta().insert('A').insert('B', {'bold': True})
    expected = Delta()
    assert a.diff(a) == expected


def test_immutability() -> None:
    attr1 = {'color': 'red'}
    attr2 = {'color': 'red'}
    a1 = Delta().insert('A', attr1)
    a2 = Delta().insert('A', attr1)
    b1 = Delta().insert('A', {'bold': True}).insert('B')
    b2 = Delta().insert('A', {'bold': True}).insert('B')
    expected = Delta().retain(1, {'bold': True, 'color': None}).insert('B')
    assert a1.diff(b1) == expected
    assert a1 == a2
    assert b2 == b2
    assert attr1 == attr2


def test_non_document() -> None:
    a = Delta().insert('Test')
    b = Delta().delete(4)
    with pytest.raises(ValueError, match='diff\\(\\) called on non-document'):
        a.diff(b)


class TestNestedAttributes:
    def test_diffs_adding_a_nested_attribute(self) -> None:
        a = Delta().insert('A')
        b = Delta().insert('A', {'comment': {'1': True}})
        expected = Delta().retain(1, {'comment': {'1': True}})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_diffs_adding_multiple_nested_attributes(self) -> None:
        a = Delta().insert('A')
        b = Delta().insert('A', {'comment': {'1': True, '2': True}})
        expected = Delta().retain(1, {'comment': {'1': True, '2': True}})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_diffs_adding_a_nested_attribute_to_an_existing_map(self) -> None:
        a = Delta().insert('A', {'comment': {'1': True, '99': True}})
        b = Delta().insert('A', {'comment': {'1': True, '99': True, '2': True}})
        expected = Delta().retain(1, {'comment': {'2': True}})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_diffs_removing_a_nested_attribute(self) -> None:
        a = Delta().insert('A', {'comment': {'1': True}})
        b = Delta().insert('A')
        expected = Delta().retain(1, {'comment': None})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_diffs_removing_a_nested_attribute_from_an_existing_map(self) -> None:
        a = Delta().insert('A', {'comment': {'1': True, '2': True}})
        b = Delta().insert('A', {'comment': {'1': True}})
        expected = Delta().retain(1, {'comment': {'2': None}})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_diffs_changing_a_nested_value(self) -> None:
        a = Delta().insert('A', {'comment': {'1': 'a', '99': 'c'}})
        b = Delta().insert('A', {'comment': {'1': 'b', '99': 'c'}})
        expected = Delta().retain(1, {'comment': {'1': 'b'}})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_diffs_adding_and_removing_nested_keys_in_the_same_map(self) -> None:
        a = Delta().insert('A', {'comment': {'1': True, '99': True}})
        b = Delta().insert('A', {'comment': {'2': True, '99': True}})
        expected = Delta().retain(1, {'comment': {'1': None, '2': True}})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_diffs_a_no_op_nested_change(self) -> None:
        a = Delta().insert('A', {'comment': {'1': True, '99': True}})
        b = Delta().insert('A', {'comment': {'1': True, '99': True}})
        expected = Delta()
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_diffs_a_deeply_nested_map_change(self) -> None:
        a = Delta().insert('A', {'comment': {'1': {'resolved': False, 'author': 'x'}}})
        b = Delta().insert('A', {'comment': {'1': {'resolved': True, 'author': 'x'}}})
        expected = Delta().retain(1, {'comment': {'1': {'resolved': True}}})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_diffs_changes_across_multiple_independent_map_attributes(self) -> None:
        a = Delta().insert('A', {'comment': {'1': True}, 'highlight': {'a': True, 'b': True}})
        b = Delta().insert('A', {'comment': {'1': True, '2': True}, 'highlight': {'b': True}})
        expected = Delta().retain(1, {'comment': {'2': True}, 'highlight': {'a': None}})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b

    def test_nested_attributes_with_the_value_undefined_are_ignored_by_diff(self) -> None:
        a = Delta().insert('A', {'comment': {'1': True}})
        b = Delta().insert('A', {'comment': {'1': True, '2': UNDEFINED}})
        diffed = a.diff(b)
        expected = Delta()
        assert diffed == expected
        assert a.compose(diffed) == a

    def test_nested_attributes_with_the_value_null_are_not_ignored_by_diff(self) -> None:
        a = Delta().insert('A', {'comment': {'1': True}})
        b = Delta().insert('A', {'comment': {'1': True, '2': None}})
        diffed = a.diff(b)
        expected = Delta().retain(1, {'comment': {'2': None}})
        assert diffed == expected
        # null attribute values on inserts are removed by compose
        assert a.compose(diffed) == Delta().insert('A', {'comment': {'1': True}})

    def test_diffs_a_nested_change_spanning_inserts(self) -> None:
        a = Delta().insert('A', {'comment': {'1': True, '99': True}}).insert('B')
        b = Delta().insert('A', {'comment': {'1': True}}).insert('B', {'comment': {'2': True}})
        expected = Delta().retain(1, {'comment': {'99': None}}).retain(1, {'comment': {'2': True}})
        diffed = a.diff(b)
        assert expected == diffed
        assert a.compose(diffed) == b
