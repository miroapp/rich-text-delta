# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import pytest

from rich_text_delta import Delta


def test_insert() -> None:
    delta = Delta().retain(2).insert('A')
    base = Delta().insert('123456')
    expected = Delta().retain(2).delete(1)
    inverted = delta.invert(base)
    assert expected == inverted
    assert base.compose(delta).compose(inverted) == base


def test_delete() -> None:
    delta = Delta().retain(2).delete(3)
    base = Delta().insert('123456')
    expected = Delta().retain(2).insert('345')
    inverted = delta.invert(base)
    assert expected == inverted
    assert base.compose(delta).compose(inverted) == base


def test_retain() -> None:
    delta = Delta().retain(2).retain(3, {'bold': True})
    base = Delta().insert('123456')
    expected = Delta().retain(2).retain(3, {'bold': None})
    inverted = delta.invert(base)
    assert expected == inverted
    assert base.compose(delta).compose(inverted) == base


def test_retain_on_a_delta_with_different_attributes() -> None:
    base = Delta().insert('123').insert('4', {'bold': True})
    delta = Delta().retain(4, {'italic': True})
    expected = Delta().retain(4, {'italic': None})
    inverted = delta.invert(base)
    assert expected == inverted
    assert base.compose(delta).compose(inverted) == base


def test_combined() -> None:
    delta = (
        Delta()
        .retain(2)
        .delete(2)
        .insert('AB', {'italic': True})
        .retain(2, {'italic': None, 'bold': True})
        .retain(2, {'color': 'red'})
        .delete(1)
    )
    base = (
        Delta()
        .insert('123', {'bold': True})
        .insert('456', {'italic': True})
        .insert('789', {'color': 'red', 'bold': True})
    )
    expected = (
        Delta()
        .retain(2)
        .insert('3', {'bold': True})
        .insert('4', {'italic': True})
        .delete(2)
        .retain(2, {'italic': True, 'bold': None})
        .retain(2)
        .insert('9', {'color': 'red', 'bold': True})
    )
    inverted = delta.invert(base)
    assert expected == inverted
    assert base.compose(delta).compose(inverted) == base


@pytest.mark.usefixtures('delta_embed')
class TestCustomEmbedHandler:
    def test_invert_a_normal_change(self) -> None:
        delta = Delta().retain(1, {'bold': True})
        base = Delta().insert({'delta': [{'insert': 'a'}]})

        expected = Delta().retain(1, {'bold': None})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_invert_an_embed_change(self) -> None:
        delta = Delta().retain({'delta': [{'insert': 'b'}]})
        base = Delta().insert({'delta': [{'insert': 'a'}]})

        expected = Delta().retain({'delta': [{'delete': 1}]})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_invert_an_embed_change_with_numbers(self) -> None:
        delta = Delta().retain(1).retain(1, {'bold': True}).retain({'delta': [{'insert': 'b'}]})
        base = Delta().insert('\n\n').insert({'delta': [{'insert': 'a'}]})

        expected = Delta().retain(1).retain(1, {'bold': None}).retain({'delta': [{'delete': 1}]})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_respects_base_attributes(self) -> None:
        delta = (
            Delta()
            .delete(1)
            .retain(1, {'header': 2})
            .retain({'delta': [{'insert': 'b'}]}, {'padding': 10, 'margin': 0})
        )
        base = (
            Delta()
            .insert('\n')
            .insert('\n', {'header': 1})
            .insert({'delta': [{'insert': 'a'}]}, {'margin': 10})
        )

        expected = (
            Delta()
            .insert('\n')
            .retain(1, {'header': 1})
            .retain({'delta': [{'delete': 1}]}, {'padding': None, 'margin': 10})
        )
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_works_with_multiple_embeds(self) -> None:
        delta = (
            Delta().retain(1).retain({'delta': [{'delete': 1}]}).retain({'delta': [{'delete': 1}]})
        )

        base = (
            Delta()
            .insert('\n')
            .insert({'delta': [{'insert': 'a'}]})
            .insert({'delta': [{'insert': 'b'}]})
        )

        expected = (
            Delta()
            .retain(1)
            .retain({'delta': [{'insert': 'a'}]})
            .retain({'delta': [{'insert': 'b'}]})
        )

        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_invert_a_string(self) -> None:
        delta = Delta().retain({'delta': [{'insert': 'a'}]})
        base = Delta().insert('a')

        with pytest.raises(ValueError, match='cannot retain a string'):
            delta.invert(base)


class TestNestedAttributes:
    def test_inverts_adding_a_nested_attribute(self) -> None:
        delta = Delta().retain(1, {'comment': {'1': True}})
        base = Delta().insert('A')
        expected = Delta().retain(1, {'comment': None})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_adding_a_multiple_nested_attributes(self) -> None:
        delta = Delta().retain(1, {'comment': {'1': True, '2': True}})
        base = Delta().insert('A')
        expected = Delta().retain(1, {'comment': None})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_adding_a_nested_attribute_to_an_existing_map(self) -> None:
        delta = Delta().retain(1, {'comment': {'2': True}})
        base = Delta().insert('A', {'comment': {'1': True, '99': True}})
        expected = Delta().retain(1, {'comment': {'2': None}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_removing_a_nested_attribute(self) -> None:
        delta = Delta().retain(1, {'comment': None})
        base = Delta().insert('A', {'comment': {'1': True}})
        expected = Delta().retain(1, {'comment': {'1': True}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_removing_a_nested_attribute_from_an_existing_map(self) -> None:
        delta = Delta().retain(1, {'comment': {'1': None}})
        base = Delta().insert('A', {'comment': {'1': True, '2': True}})
        expected = Delta().retain(1, {'comment': {'1': True}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_a_nested_attribute_change_that_split_an_insert(self) -> None:
        delta = Delta().retain(1, {'comment': {'2': True}})
        base = Delta().insert('AB', {'comment': {'1': True, '99': True}})
        expected = Delta().retain(1, {'comment': {'2': None}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_removing_a_nested_attribute_that_would_remove_the_outer_map(self) -> None:
        delta = Delta().retain(1, {'comment': {'1': None}})
        base = Delta().insert('A', {'comment': {'1': True}})
        expected = Delta().retain(1, {'comment': {'1': True}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_removing_a_nested_attribute_change_that_joined_inserts(self) -> None:
        delta = Delta().retain(1).retain(1, {'comment': {'2': None}})
        base = (
            Delta()
            .insert('A', {'comment': {'1': True}})
            .insert('B', {'comment': {'1': True, '2': True}})
        )
        expected = Delta().retain(1).retain(1, {'comment': {'2': True}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_changing_a_nested_value(self) -> None:
        delta = Delta().retain(1, {'comment': {'1': 'b'}})
        base = Delta().insert('A', {'comment': {'1': 'a', '99': 'c'}})
        expected = Delta().retain(1, {'comment': {'1': 'a'}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_adding_and_removing_nested_keys_in_the_same_map(self) -> None:
        delta = Delta().retain(1, {'comment': {'1': None, '2': True}})
        base = Delta().insert('A', {'comment': {'1': True, '99': True}})
        expected = Delta().retain(1, {'comment': {'1': True, '2': None}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_a_no_op_nested_change(self) -> None:
        delta = Delta().retain(1, {'comment': {'1': True}})
        base = Delta().insert('A', {'comment': {'1': True, '99': True}})
        expected = Delta()
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_a_deeply_nested_map_change(self) -> None:
        delta = Delta().retain(1, {'comment': {'1': {'resolved': True}}})
        base = Delta().insert(
            'A', {'comment': {'1': {'resolved': False, 'author': 'x'}, '99': True}}
        )
        expected = Delta().retain(1, {'comment': {'1': {'resolved': False}}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_changes_across_multiple_independent_map_attributes(self) -> None:
        delta = Delta().retain(1, {'comment': {'2': True}, 'highlight': {'a': None}})
        base = Delta().insert(
            'A',
            {
                'comment': {'1': True, '5': True},
                'highlight': {'a': True, 'b': True},
                'bold': True,
            },
        )
        expected = Delta().retain(1, {'comment': {'2': None}, 'highlight': {'a': True}})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base

    def test_inverts_a_nested_change_spanning_inserts_where_one_lacks_the_map(self) -> None:
        delta = Delta().retain(2, {'comment': {'2': True}})
        base = Delta().insert('A', {'comment': {'1': True, '99': True}}).insert('B')
        expected = Delta().retain(1, {'comment': {'2': None}}).retain(1, {'comment': None})
        inverted = delta.invert(base)
        assert expected == inverted
        assert base.compose(delta).compose(inverted) == base
