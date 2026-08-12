# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from typing import Any, Dict

import pytest

from rich_text_delta import Delta


def test_insert_plus_insert() -> None:
    a = Delta().insert('A')
    b = Delta().insert('B')
    expected = Delta().insert('B').insert('A')
    assert a.compose(b) == expected


def test_insert_plus_retain() -> None:
    a = Delta().insert('A')
    b = Delta().retain(1, {'bold': True, 'color': 'red', 'font': None})
    expected = Delta().insert('A', {'bold': True, 'color': 'red'})
    assert a.compose(b) == expected


def test_insert_plus_delete() -> None:
    a = Delta().insert('A')
    b = Delta().delete(1)
    expected = Delta()
    assert a.compose(b) == expected


def test_delete_plus_insert() -> None:
    a = Delta().delete(1)
    b = Delta().insert('B')
    expected = Delta().insert('B').delete(1)
    assert a.compose(b) == expected


def test_delete_plus_retain() -> None:
    a = Delta().delete(1)
    b = Delta().retain(1, {'bold': True, 'color': 'red'})
    expected = Delta().delete(1).retain(1, {'bold': True, 'color': 'red'})
    assert a.compose(b) == expected


def test_delete_plus_delete() -> None:
    a = Delta().delete(1)
    b = Delta().delete(1)
    expected = Delta().delete(2)
    assert a.compose(b) == expected


def test_retain_plus_insert() -> None:
    a = Delta().retain(1, {'color': 'blue'})
    b = Delta().insert('B')
    expected = Delta().insert('B').retain(1, {'color': 'blue'})
    assert a.compose(b) == expected


def test_retain_plus_retain() -> None:
    a = Delta().retain(1, {'color': 'blue'})
    b = Delta().retain(1, {'bold': True, 'color': 'red', 'font': None})
    expected = Delta().retain(1, {'bold': True, 'color': 'red', 'font': None})
    assert a.compose(b) == expected


def test_retain_plus_delete() -> None:
    a = Delta().retain(1, {'color': 'blue'})
    b = Delta().delete(1)
    expected = Delta().delete(1)
    assert a.compose(b) == expected


def test_insert_in_middle_of_text() -> None:
    a = Delta().insert('Hello')
    b = Delta().retain(3).insert('X')
    expected = Delta().insert('HelXlo')
    assert a.compose(b) == expected


def test_insert_and_delete_ordering() -> None:
    a = Delta().insert('Hello')
    b = Delta().insert('Hello')
    insert_first = Delta().retain(3).insert('X').delete(1)
    delete_first = Delta().retain(3).delete(1).insert('X')
    expected = Delta().insert('HelXo')
    assert a.compose(insert_first) == expected
    assert b.compose(delete_first) == expected


def test_insert_embed() -> None:
    a = Delta().insert({'embed': 1}, {'src': 'http://quilljs.com/image.png'})
    b = Delta().retain(1, {'alt': 'logo'})
    expected = Delta().insert(
        {'embed': 1},
        {'src': 'http://quilljs.com/image.png', 'alt': 'logo'},
    )
    assert a.compose(b) == expected


def test_retain_embed() -> None:
    a = Delta().retain({'figure': True}, {'src': 'http://quilljs.com/image.png'})
    b = Delta().retain(1, {'alt': 'logo'})
    expected = Delta().retain(
        {'figure': True},
        {'src': 'http://quilljs.com/image.png', 'alt': 'logo'},
    )
    assert a.compose(b) == expected


def test_delete_entire_text() -> None:
    a = Delta().retain(4).insert('Hello')
    b = Delta().delete(9)
    expected = Delta().delete(4)
    assert a.compose(b) == expected


def test_retain_more_than_length_of_text() -> None:
    a = Delta().insert('Hello')
    b = Delta().retain(10)
    expected = Delta().insert('Hello')
    assert a.compose(b) == expected


def test_retain_empty_embed() -> None:
    a = Delta().insert({'embed': 1})
    b = Delta().retain(1)
    expected = Delta().insert({'embed': 1})
    assert a.compose(b) == expected


def test_remove_all_attributes() -> None:
    a = Delta().insert('A', {'bold': True})
    b = Delta().retain(1, {'bold': None})
    expected = Delta().insert('A')
    assert a.compose(b) == expected


def test_remove_all_embed_attributes() -> None:
    a = Delta().insert({'embed': 2}, {'bold': True})
    b = Delta().retain(1, {'bold': None})
    expected = Delta().insert({'embed': 2})
    assert a.compose(b) == expected


def test_add_nested_attributes() -> None:
    a = Delta().insert('A')
    b = Delta().retain(1, {'comment': {'1': True}})
    expected = Delta().insert('A', {'comment': {'1': True}})
    assert a.compose(b) == expected


def test_add_nested_attribute_to_existing_object() -> None:
    a = Delta().insert('A', {'comment': {'1': True}})
    b = Delta().retain(1, {'comment': {'2': True}})
    expected = Delta().insert('A', {'comment': {'1': True, '2': True}})
    assert a.compose(b) == expected


def test_remove_nested_attributes() -> None:
    a = Delta().insert('A', {'comment': {'1': True, '2': True}})
    b = Delta().retain(1, {'comment': {'2': None}})
    expected = Delta().insert('A', {'comment': {'1': True}})
    assert a.compose(b) == expected


def test_nested_attributes_splits_inserts() -> None:
    a = Delta().insert('AB', {'comment': {'1': True}})
    b = Delta().retain(1, {'comment': {'2': True}})
    expected = (
        Delta()
        .insert('A', {'comment': {'1': True, '2': True}})
        .insert('B', {'comment': {'1': True}})
    )
    assert a.compose(b) == expected


def test_nested_attributes_joins_inserts() -> None:
    a = (
        Delta()
        .insert('A', {'comment': {'1': True, '2': True}})
        .insert('B', {'comment': {'1': True}})
    )
    b = Delta().retain(1).retain(1, {'comment': {'2': True}})
    expected = Delta().insert('AB', {'comment': {'1': True, '2': True}})
    assert a.compose(b) == expected


def test_top_level_null_removes_all_nested_attributes() -> None:
    a = Delta().insert('A', {'suggestion': {'1': {'bold': True}, '2': {'underline': True}}})
    b = Delta().retain(1, {'suggestion': None})
    expected = Delta().insert('A')
    assert a.compose(b) == expected


def test_removing_final_key_in_nested_object_removes_outer_key() -> None:
    a = Delta().insert('A', {'suggestion': {'1': {'bold': True}, '2': {'underline': True}}})
    b = Delta().retain(1, {'suggestion': {'1': {'bold': None}}})
    expected = Delta().insert('A', {'suggestion': {'2': {'underline': True}}})
    assert a.compose(b) == expected


def test_changes_a_nested_value() -> None:
    a = Delta().insert('A', {'comment': {'1': 'a', '99': 'keep'}})
    b = Delta().retain(1, {'comment': {'1': 'b'}})
    expected = Delta().insert('A', {'comment': {'1': 'b', '99': 'keep'}})
    assert a.compose(b) == expected


def test_adds_and_removes_nested_keys_in_the_same_map() -> None:
    a = Delta().insert('A', {'comment': {'1': True, '99': True}})
    b = Delta().retain(1, {'comment': {'1': None, '2': True}})
    expected = Delta().insert('A', {'comment': {'2': True, '99': True}})
    assert a.compose(b) == expected


def test_no_op_nested_change_keeps_existing_attributes() -> None:
    a = Delta().insert('A', {'comment': {'1': True, '99': True}})
    b = Delta().retain(1, {'comment': {'1': True}})
    expected = Delta().insert('A', {'comment': {'1': True, '99': True}})
    assert a.compose(b) == expected


def test_composes_a_deeply_nested_map_change() -> None:
    a = Delta().insert('A', {'comment': {'1': {'resolved': False, 'author': 'x'}}})
    b = Delta().retain(1, {'comment': {'1': {'resolved': True}}})
    expected = Delta().insert('A', {'comment': {'1': {'resolved': True, 'author': 'x'}}})
    assert a.compose(b) == expected


def test_composes_changes_across_multiple_independent_map_attributes() -> None:
    a = Delta().insert('A', {'comment': {'1': True}, 'highlight': {'a': True}})
    b = Delta().retain(1, {'comment': {'2': True}, 'highlight': {'a': None}})
    expected = Delta().insert('A', {'comment': {'1': True, '2': True}})
    assert a.compose(b) == expected


def test_composes_a_nested_change_spanning_inserts_where_one_lacks_the_map() -> None:
    a = Delta().insert('A', {'comment': {'1': True}}).insert('B')
    b = Delta().retain(2, {'comment': {'2': True}})
    expected = (
        Delta()
        .insert('A', {'comment': {'1': True, '2': True}})
        .insert('B', {'comment': {'2': True}})
    )
    assert a.compose(b) == expected


def test_preserves_nested_null_when_composing_two_change_deltas() -> None:
    a = Delta().retain(1, {'comment': {'1': True}})
    b = Delta().retain(1, {'comment': {'1': None}})
    expected = Delta().retain(1, {'comment': {'1': None}})
    assert a.compose(b) == expected


def test_strips_nested_null_when_composing_onto_an_insert() -> None:
    a = Delta().insert('A', {'comment': {'1': True}})
    b = Delta().retain(1, {'comment': {'1': None}})
    expected = Delta().insert('A')
    assert a.compose(b) == expected


def test_does_not_share_nested_map_references_with_the_source_delta() -> None:
    a = Delta().insert('A')
    b = Delta().retain(1, {'comment': {'1': True}})
    composed = a.compose(b)
    attributes = composed.ops[0]['attributes']
    assert isinstance(attributes, dict)
    comment: Dict[str, Any] = attributes['comment']
    comment['2'] = True
    assert b.ops[0]['attributes'] == {'comment': {'1': True}}


def test_immutability() -> None:
    attr1 = {'bold': True}
    attr2 = {'bold': True}
    a1 = Delta().insert('Test', attr1)
    a2 = Delta().insert('Test', attr1)
    b1 = Delta().retain(1, {'color': 'red'}).delete(2)
    b2 = Delta().retain(1, {'color': 'red'}).delete(2)
    expected = Delta().insert('T', {'color': 'red', 'bold': True}).insert('t', attr1)
    assert a1.compose(b1) == expected
    assert a1 == a2
    assert b1 == b2
    assert attr1 == attr2


def test_retain_start_optimization() -> None:
    a = Delta().insert('A', {'bold': True}).insert('B').insert('C', {'bold': True}).delete(1)
    b = Delta().retain(3).insert('D')
    expected = (
        Delta()
        .insert('A', {'bold': True})
        .insert('B')
        .insert('C', {'bold': True})
        .insert('D')
        .delete(1)
    )
    assert a.compose(b) == expected


def test_retain_start_optimization_split() -> None:
    a = (
        Delta()
        .insert('A', {'bold': True})
        .insert('B')
        .insert('C', {'bold': True})
        .retain(5)
        .delete(1)
    )
    b = Delta().retain(4).insert('D')
    expected = (
        Delta()
        .insert('A', {'bold': True})
        .insert('B')
        .insert('C', {'bold': True})
        .retain(1)
        .insert('D')
        .retain(4)
        .delete(1)
    )
    assert a.compose(b) == expected


def test_retain_end_optimization() -> None:
    a = Delta().insert('A', {'bold': True}).insert('B').insert('C', {'bold': True})
    b = Delta().delete(1)
    expected = Delta().insert('B').insert('C', {'bold': True})
    assert a.compose(b) == expected


def test_retain_end_optimization_join() -> None:
    a = (
        Delta()
        .insert('A', {'bold': True})
        .insert('B')
        .insert('C', {'bold': True})
        .insert('D')
        .insert('E', {'bold': True})
        .insert('F')
    )
    b = Delta().retain(1).delete(1)
    expected = (
        Delta().insert('AC', {'bold': True}).insert('D').insert('E', {'bold': True}).insert('F')
    )
    assert a.compose(b) == expected


@pytest.mark.usefixtures('delta_embed')
class TestCustomEmbedHandler:
    def test_retain_an_embed_with_a_number(self) -> None:
        a = Delta().insert({'delta': [{'insert': 'a'}]})
        b = Delta().retain(1, {'bold': True})
        expected = Delta().insert({'delta': [{'insert': 'a'}]}, {'bold': True})
        assert a.compose(b) == expected

    def test_retain_a_number_with_an_embed(self) -> None:
        a = Delta().retain(10, {'bold': True})
        b = Delta().retain({'delta': [{'insert': 'b'}]})
        expected = (
            Delta().retain({'delta': [{'insert': 'b'}]}, {'bold': True}).retain(9, {'bold': True})
        )
        assert a.compose(b) == expected

    def test_retain_an_embed_with_an_embed(self) -> None:
        a = Delta().insert({'delta': [{'insert': 'a'}]})
        b = Delta().retain({'delta': [{'insert': 'b'}]})
        expected = Delta().insert({'delta': [{'insert': 'ba'}]})
        assert a.compose(b) == expected

    def test_keeps_other_delete_when_this_op_is_a_retain(self) -> None:
        a = Delta().retain({'delta': [{'insert': 'a'}]})
        b = Delta().insert('\n').delete(1)
        expected = Delta().insert('\n').delete(1)
        assert a.compose(b) == expected

    def test_retain_an_embed_with_another_type_of_embed(self) -> None:
        a = Delta().insert({'delta': [{'insert': 'a'}]})
        b = Delta().retain({'otherdelta': [{'insert': 'b'}]})
        with pytest.raises(ValueError, match=r'^embed types not matched: delta != otherdelta$'):
            a.compose(b)

    def test_retain_a_string_with_an_embed(self) -> None:
        a = Delta().insert('a')
        b = Delta().retain({'delta': [{'insert': 'b'}]})
        with pytest.raises(ValueError, match=r'^cannot retain a string$'):
            a.compose(b)

    def test_retain_embeds_without_a_handler(self) -> None:
        a = Delta().insert({'mydelta': [{'insert': 'a'}]})
        b = Delta().retain({'mydelta': [{'insert': 'b'}]})
        with pytest.raises(ValueError, match=r'^no handlers for embed type "mydelta"$'):
            a.compose(b)
