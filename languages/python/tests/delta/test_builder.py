# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from typing import List

from rich_text_delta import Delta, Op


class TestConstructor:
    ops: List[Op] = [
        {'insert': 'abc'},
        {'retain': 1, 'attributes': {'color': 'red'}},
        {'delete': 4},
        {'insert': 'def', 'attributes': {'bold': True}},
        {'retain': 6},
    ]

    def test_empty(self) -> None:
        delta = Delta()
        assert delta is not None
        assert delta.ops is not None
        assert len(delta.ops) == 0

    def test_empty_ops(self) -> None:
        delta = Delta().insert('').delete(0).retain(0)
        assert delta is not None
        assert delta.ops is not None
        assert len(delta.ops) == 0

    def test_list_of_ops(self) -> None:
        delta = Delta(self.ops)
        assert delta.ops == self.ops

    def test_delta_in_dict_form(self) -> None:
        delta = Delta({'ops': self.ops})
        assert delta.ops == self.ops

    def test_delta(self) -> None:
        original = Delta(self.ops)
        delta = Delta(original)
        assert delta.ops == original.ops
        assert delta.ops == self.ops


class TestInsert:
    def test_insert_text(self) -> None:
        delta = Delta().insert('test')
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'insert': 'test'}

    def test_insert_text_none(self) -> None:
        delta = Delta().insert('test', None)
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'insert': 'test'}

    def test_insert_embed(self) -> None:
        delta = Delta().insert({'embed': 1})
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'insert': {'embed': 1}}

    def test_insert_embed_attributes(self) -> None:
        obj = {'url': 'http://quilljs.com', 'alt': 'Quill'}
        delta = Delta().insert({'embed': 1}, obj)
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'insert': {'embed': 1}, 'attributes': obj}

    def test_insert_embed_non_integer(self) -> None:
        embed = {'url': 'http://quilljs.com'}
        attr = {'alt': 'Quill'}
        delta = Delta().insert(embed, attr)
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'insert': embed, 'attributes': attr}

    def test_insert_text_attributes(self) -> None:
        delta = Delta().insert('test', {'bold': True})
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'insert': 'test', 'attributes': {'bold': True}}

    def test_insert_text_after_delete(self) -> None:
        delta = Delta().delete(1).insert('a')
        expected = Delta().insert('a').delete(1)
        assert delta == expected

    def test_insert_text_after_delete_with_merge(self) -> None:
        delta = Delta().insert('a').delete(1).insert('b')
        expected = Delta().insert('ab').delete(1)
        assert delta == expected

    def test_insert_text_after_delete_no_merge(self) -> None:
        delta = Delta().insert({'embed': 1}).delete(1).insert('a')
        expected = Delta().insert({'embed': 1}).insert('a').delete(1)
        assert delta == expected

    def test_insert_text_empty_attributes(self) -> None:
        delta = Delta().insert('a', {})
        expected = Delta().insert('a')
        assert delta == expected


class TestDelete:
    def test_delete_zero(self) -> None:
        delta = Delta().delete(0)
        assert len(delta.ops) == 0

    def test_delete_positive(self) -> None:
        delta = Delta().delete(1)
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'delete': 1}


class TestRetain:
    def test_retain_zero(self) -> None:
        delta = Delta().retain(0)
        assert len(delta.ops) == 0

    def test_retain_length(self) -> None:
        delta = Delta().retain(2)
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'retain': 2}

    def test_retain_length_none(self) -> None:
        delta = Delta().retain(2, None)
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'retain': 2}

    def test_retain_length_attributes(self) -> None:
        delta = Delta().retain(1, {'bold': True})
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'retain': 1, 'attributes': {'bold': True}}

    def test_retain_length_empty_attributes(self) -> None:
        delta = Delta().retain(2, {}).delete(1)  # Delete prevents chop
        expected = Delta().retain(2).delete(1)
        assert delta == expected


class TestPush:
    def test_push_into_empty(self) -> None:
        delta = Delta()
        delta.push({'insert': 'test'})
        assert len(delta.ops) == 1

    def test_push_consecutive_delete(self) -> None:
        delta = Delta().delete(2)
        delta.push({'delete': 3})
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'delete': 5}

    def test_push_consecutive_text(self) -> None:
        delta = Delta().insert('a')
        delta.push({'insert': 'b'})
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'insert': 'ab'}

    def test_push_consecutive_texts_with_matching_attributes(self) -> None:
        delta = Delta().insert('a', {'bold': True})
        delta.push({'insert': 'b', 'attributes': {'bold': True}})
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'insert': 'ab', 'attributes': {'bold': True}}

    def test_push_consecutive_retains_with_matching_attributes(self) -> None:
        delta = Delta().retain(1, {'bold': True})
        delta.push({'retain': 3, 'attributes': {'bold': True}})
        assert len(delta.ops) == 1
        assert delta.ops[0] == {'retain': 4, 'attributes': {'bold': True}}

    def test_push_consecutive_texts_with_mismatched_attributes(self) -> None:
        delta = Delta().insert('a', {'bold': True})
        delta.push({'insert': 'b'})
        assert len(delta.ops) == 2

    def test_push_consecutive_retains_with_mismatched_attributes(self) -> None:
        delta = Delta().retain(1, {'bold': True})
        delta.push({'retain': 3})
        assert len(delta.ops) == 2

    def test_push_consecutive_embeds_with_matching_attributes(self) -> None:
        delta = Delta().insert({'embed': 1}, {'alt': 'Description'})
        delta.push(
            {
                'insert': {'url': 'http://quilljs.com'},
                'attributes': {'alt': 'Description'},
            }
        )
        assert len(delta.ops) == 2
