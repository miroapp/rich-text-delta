# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import pytest
from conftest import transform_delta

from rich_text_delta import Delta


def test_insert_plus_insert() -> None:
    a1 = Delta().insert('A')
    b1 = Delta().insert('B')
    a2 = Delta(a1)
    b2 = Delta(b1)
    expected1 = Delta().retain(1).insert('B')
    expected2 = Delta().insert('B')
    assert transform_delta(a1, b1, True) == expected1
    assert transform_delta(a2, b2, False) == expected2


def test_insert_plus_retain() -> None:
    a = Delta().insert('A')
    b = Delta().retain(1, {'bold': True, 'color': 'red'})
    expected = Delta().retain(1).retain(1, {'bold': True, 'color': 'red'})
    assert transform_delta(a, b, True) == expected


def test_insert_plus_delete() -> None:
    a = Delta().insert('A')
    b = Delta().delete(1)
    expected = Delta().retain(1).delete(1)
    assert transform_delta(a, b, True) == expected


def test_delete_plus_insert() -> None:
    a = Delta().delete(1)
    b = Delta().insert('B')
    expected = Delta().insert('B')
    assert transform_delta(a, b, True) == expected


def test_delete_plus_retain() -> None:
    a = Delta().delete(1)
    b = Delta().retain(1, {'bold': True, 'color': 'red'})
    expected = Delta()
    assert transform_delta(a, b, True) == expected


def test_delete_plus_delete() -> None:
    a = Delta().delete(1)
    b = Delta().delete(1)
    expected = Delta()
    assert transform_delta(a, b, True) == expected


def test_retain_plus_insert() -> None:
    a = Delta().retain(1, {'color': 'blue'})
    b = Delta().insert('B')
    expected = Delta().insert('B')
    assert transform_delta(a, b, True) == expected


def test_retain_plus_retain() -> None:
    a1 = Delta().retain(1, {'color': 'blue'})
    b1 = Delta().retain(1, {'bold': True, 'color': 'red'})
    a2 = Delta().retain(1, {'color': 'blue'})
    b2 = Delta().retain(1, {'bold': True, 'color': 'red'})
    expected1 = Delta().retain(1, {'bold': True})
    expected2 = Delta()
    assert transform_delta(a1, b1, True) == expected1
    assert transform_delta(b2, a2, True) == expected2


def test_retain_plus_retain_without_priority() -> None:
    a1 = Delta().retain(1, {'color': 'blue'})
    b1 = Delta().retain(1, {'bold': True, 'color': 'red'})
    a2 = Delta().retain(1, {'color': 'blue'})
    b2 = Delta().retain(1, {'bold': True, 'color': 'red'})
    expected1 = Delta().retain(1, {'bold': True, 'color': 'red'})
    expected2 = Delta().retain(1, {'color': 'blue'})
    assert transform_delta(a1, b1, False) == expected1
    assert transform_delta(b2, a2, False) == expected2


class TestNestedAttributes:
    def test_retain_plus_retain_with_nesting_on_mutually_exclusive_nested_attributes(
        self,
    ) -> None:
        a = Delta().retain(1, {'comment': {'1': True}})
        b = Delta().retain(1, {'comment': {'2': True}})

        expected1 = Delta().retain(1, {'comment': {'1': True}})
        expected2 = Delta().retain(1, {'comment': {'2': True}})
        assert transform_delta(b, a, True) == expected1
        assert transform_delta(b, a, False) == expected1
        assert transform_delta(a, b, True) == expected2
        assert transform_delta(a, b, False) == expected2

    def test_retain_plus_retain_with_nesting_on_overlapping_nested_attributes(self) -> None:
        a = Delta().retain(1, {'comment': {'1': True}})
        b = Delta().retain(1, {'comment': {'1': None, '2': True}})

        assert transform_delta(b, a, True) == Delta()
        assert transform_delta(b, a, False) == a
        assert transform_delta(a, b, True) == Delta().retain(1, {'comment': {'2': True}})
        assert transform_delta(a, b, False) == b

    def test_retain_plus_retain_with_nesting_on_overriding_nested_attributes(self) -> None:
        a = Delta().retain(1, {'comment': {'1': True}})
        b = Delta().retain(1, {'comment': None})

        assert transform_delta(b, a, True) == Delta()
        assert transform_delta(b, a, False) == a
        assert transform_delta(a, b, True) == Delta()
        assert transform_delta(a, b, False) == b

    def test_retain_plus_retain_with_both_null(self) -> None:
        a = Delta().retain(1, {'bold': None})
        b = Delta().retain(1, {'bold': None})

        assert transform_delta(b, a, True) == Delta()
        assert transform_delta(b, a, False) == Delta().retain(1, {'bold': None})
        assert transform_delta(a, b, True) == Delta()
        assert transform_delta(a, b, False) == Delta().retain(1, {'bold': None})

    def test_retain_plus_retain_with_nesting_and_both_null(self) -> None:
        a = Delta().retain(1, {'comment': {'1': None}})
        b = Delta().retain(1, {'comment': {'1': None}})

        assert transform_delta(b, a, True) == Delta()
        assert transform_delta(b, a, False) == Delta().retain(1, {'comment': {'1': None}})
        assert transform_delta(a, b, True) == Delta()
        assert transform_delta(a, b, False) == Delta().retain(1, {'comment': {'1': None}})

    def test_retain_plus_retain_with_nesting_changing_the_same_nested_value(self) -> None:
        a = Delta().retain(1, {'comment': {'1': 'a'}})
        b = Delta().retain(1, {'comment': {'1': 'b'}})

        assert transform_delta(a, b, True) == Delta()
        assert transform_delta(a, b, False) == b
        assert transform_delta(b, a, True) == Delta()
        assert transform_delta(b, a, False) == a

    def test_retain_plus_retain_with_nesting_adding_and_removing_keys_in_the_same_map(
        self,
    ) -> None:
        a = Delta().retain(1, {'comment': {'1': None, '2': True}})
        b = Delta().retain(1, {'comment': {'1': True, '3': True}})

        assert transform_delta(a, b, True) == Delta().retain(1, {'comment': {'3': True}})
        assert transform_delta(a, b, False) == b
        assert transform_delta(b, a, True) == Delta().retain(1, {'comment': {'2': True}})
        assert transform_delta(b, a, False) == a

    def test_retain_plus_retain_with_deeply_nested_non_conflicting_attributes(self) -> None:
        a = Delta().retain(1, {'comment': {'1': {'bold': True}}})
        b = Delta().retain(1, {'comment': {'1': {'italic': True}}})

        assert transform_delta(a, b, True) == Delta().retain(
            1, {'comment': {'1': {'italic': True}}}
        )
        assert transform_delta(a, b, False) == b
        assert transform_delta(b, a, True) == Delta().retain(1, {'comment': {'1': {'bold': True}}})
        assert transform_delta(b, a, False) == a

    def test_retain_plus_retain_across_multiple_independent_map_attributes(self) -> None:
        a = Delta().retain(1, {'comment': {'1': True}, 'highlight': {'a': True}})
        b = Delta().retain(1, {'comment': {'2': True}, 'highlight': {'a': False}})

        assert transform_delta(a, b, True) == Delta().retain(1, {'comment': {'2': True}})
        assert transform_delta(a, b, False) == b
        assert transform_delta(b, a, True) == Delta().retain(1, {'comment': {'1': True}})
        assert transform_delta(b, a, False) == a


class TestNestedAttributeConvergence:
    @staticmethod
    def converges(base: Delta, a: Delta, b: Delta) -> None:
        ab = base.compose(a).compose(transform_delta(a, b, False))
        ba = base.compose(b).compose(transform_delta(b, a, True))
        assert ab == ba

    def test_disjoint_ids_merge(self) -> None:
        self.converges(
            Delta().insert('A'),
            Delta().retain(1, {'comment': {'1': True}}),
            Delta().retain(1, {'comment': {'2': True}}),
        )

    def test_same_leaf_conflict_resolves_consistently(self) -> None:
        self.converges(
            Delta().insert('A'),
            Delta().retain(1, {'comment': {'1': 'a'}}),
            Delta().retain(1, {'comment': {'1': 'b'}}),
        )

    def test_add_vs_delete_of_the_same_id(self) -> None:
        self.converges(
            Delta().insert('A', {'comment': {'1': True}}),
            Delta().retain(1, {'comment': {'1': None}}),
            Delta().retain(1, {'comment': {'1': 'changed'}}),
        )


def test_retain_plus_delete() -> None:
    a = Delta().retain(1, {'color': 'blue'})
    b = Delta().delete(1)
    expected = Delta().delete(1)
    assert transform_delta(a, b, True) == expected


def test_alternating_edits() -> None:
    a1 = Delta().retain(2).insert('si').delete(5)
    b1 = Delta().retain(1).insert('e').delete(5).retain(1).insert('ow')
    a2 = Delta(a1)
    b2 = Delta(b1)
    expected1 = Delta().retain(1).insert('e').delete(1).retain(2).insert('ow')
    expected2 = Delta().retain(2).insert('si').delete(1)
    assert transform_delta(a1, b1, False) == expected1
    assert transform_delta(b2, a2, False) == expected2


def test_conflicting_appends() -> None:
    a1 = Delta().retain(3).insert('aa')
    b1 = Delta().retain(3).insert('bb')
    a2 = Delta(a1)
    b2 = Delta(b1)
    expected1 = Delta().retain(5).insert('bb')
    expected2 = Delta().retain(3).insert('aa')
    assert transform_delta(a1, b1, True) == expected1
    assert transform_delta(b2, a2, False) == expected2


def test_prepend_plus_append() -> None:
    a1 = Delta().insert('aa')
    b1 = Delta().retain(3).insert('bb')
    expected1 = Delta().retain(5).insert('bb')
    a2 = Delta(a1)
    b2 = Delta(b1)
    expected2 = Delta().insert('aa')
    assert transform_delta(a1, b1, False) == expected1
    assert transform_delta(b2, a2, False) == expected2


def test_trailing_deletes_with_differing_lengths() -> None:
    a1 = Delta().retain(2).delete(1)
    b1 = Delta().delete(3)
    expected1 = Delta().delete(2)
    a2 = Delta(a1)
    b2 = Delta(b1)
    expected2 = Delta()
    assert transform_delta(a1, b1, False) == expected1
    assert transform_delta(b2, a2, False) == expected2


def test_immutability() -> None:
    a1 = Delta().insert('A')
    a2 = Delta().insert('A')
    b1 = Delta().insert('B')
    b2 = Delta().insert('B')
    expected = Delta().retain(1).insert('B')
    assert transform_delta(a1, b1, True) == expected
    assert a1 == a2
    assert b1 == b2


@pytest.mark.usefixtures('delta_embed')
class TestCustomEmbedHandler:
    def test_transform_an_embed_change_with_number(self) -> None:
        a = Delta().retain(1)
        b = Delta().retain({'delta': [{'insert': 'b'}]})
        expected = Delta().retain({'delta': [{'insert': 'b'}]})
        assert transform_delta(a, b, True) == expected
        assert transform_delta(a, b) == expected

    def test_transform_an_embed_change(self) -> None:
        a = Delta().retain({'delta': [{'insert': 'a'}]})
        b = Delta().retain({'delta': [{'insert': 'b'}]})
        expected1 = Delta().retain({'delta': [{'retain': 1}, {'insert': 'b'}]})
        expected2 = Delta().retain({'delta': [{'insert': 'b'}]})
        assert transform_delta(a, b, True) == expected1
        assert transform_delta(a, b) == expected2
