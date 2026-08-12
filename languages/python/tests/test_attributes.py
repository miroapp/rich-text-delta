# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import json
from typing import Any, Dict

from rich_text_delta import attribute_map

AttributeMap = Dict[str, Any]


class TestCompose:
    attributes = {'bold': True, 'color': 'red'}

    def test_left_is_undefined(self) -> None:
        assert attribute_map.compose(None, self.attributes) == self.attributes

    def test_right_is_undefined(self) -> None:
        assert attribute_map.compose(self.attributes, None) == self.attributes

    def test_both_are_undefined(self) -> None:
        assert attribute_map.compose(None, None) is None

    def test_missing(self) -> None:
        assert attribute_map.compose(self.attributes, {'italic': True}) == {
            'bold': True,
            'italic': True,
            'color': 'red',
        }

    def test_overwrite(self) -> None:
        assert attribute_map.compose(self.attributes, {'bold': False, 'color': 'blue'}) == {
            'bold': False,
            'color': 'blue',
        }

    def test_remove(self) -> None:
        assert attribute_map.compose(self.attributes, {'bold': None}) == {'color': 'red'}

    def test_remove_to_none(self) -> None:
        assert attribute_map.compose(self.attributes, {'bold': None, 'color': None}) is None

    def test_remove_missing(self) -> None:
        assert attribute_map.compose(self.attributes, {'italic': None}) == self.attributes


class TestDiff:
    format = {'bold': True, 'color': 'red'}

    def test_left_is_undefined(self) -> None:
        assert attribute_map.diff(None, self.format) == self.format

    def test_right_is_undefined(self) -> None:
        expected = {'bold': None, 'color': None}
        assert attribute_map.diff(self.format, None) == expected

    def test_same_format(self) -> None:
        assert attribute_map.diff(self.format, self.format) is None

    def test_add_format(self) -> None:
        added = {'bold': True, 'italic': True, 'color': 'red'}
        expected = {'italic': True}
        assert attribute_map.diff(self.format, added) == expected

    def test_remove_format(self) -> None:
        removed = {'bold': True}
        expected = {'color': None}
        assert attribute_map.diff(self.format, removed) == expected

    def test_overwrite_format(self) -> None:
        overwritten = {'bold': True, 'color': 'blue'}
        expected = {'color': 'blue'}
        assert attribute_map.diff(self.format, overwritten) == expected


class TestInvert:
    def test_attributes_is_undefined(self) -> None:
        base = {'bold': True}
        assert attribute_map.invert(None, base) == {}

    def test_base_is_undefined(self) -> None:
        attributes = {'bold': True}
        expected = {'bold': None}
        assert attribute_map.invert(attributes, None) == expected

    def test_both_undefined(self) -> None:
        assert attribute_map.invert() == {}

    def test_merge(self) -> None:
        attributes = {'bold': True}
        base = {'italic': True}
        expected = {'bold': None}
        assert attribute_map.invert(attributes, base) == expected

    def test_null(self) -> None:
        attributes = {'bold': None}
        base = {'bold': True}
        expected = {'bold': True}
        assert attribute_map.invert(attributes, base) == expected

    def test_replace(self) -> None:
        attributes = {'color': 'red'}
        base = {'color': 'blue'}
        expected = base
        assert attribute_map.invert(attributes, base) == expected

    def test_noop(self) -> None:
        attributes = {'color': 'red'}
        base = {'color': 'red'}
        expected: AttributeMap = {}
        assert attribute_map.invert(attributes, base) == expected

    def test_combined(self) -> None:
        attributes = {
            'bold': True,
            'italic': None,
            'color': 'red',
            'size': '12px',
        }
        base = {'font': 'serif', 'italic': True, 'color': 'blue', 'size': '12px'}
        expected = {'bold': None, 'italic': True, 'color': 'blue'}
        assert attribute_map.invert(attributes, base) == expected


class TestListValues:
    """Lists are atomic, last write wins (arrays in the TypeScript suite)."""

    def test_compose_overwrites_the_whole_list(self) -> None:
        assert attribute_map.compose({'ids': [1, 2]}, {'ids': [3]}) == {'ids': [3]}

    def test_compose_keeps_a_list_untouched_by_the_other_side(self) -> None:
        assert attribute_map.compose({'ids': [1, 2]}, {'other': True}) == {
            'ids': [1, 2],
            'other': True,
        }

    def test_diff_yields_the_whole_new_list(self) -> None:
        assert attribute_map.diff({'ids': [1, 2]}, {'ids': [3]}) == {'ids': [3]}

    def test_diff_of_equal_lists_is_a_noop(self) -> None:
        assert attribute_map.diff({'ids': [1, 2]}, {'ids': [1, 2]}) is None

    def test_invert_restores_the_base_list(self) -> None:
        assert attribute_map.invert({'ids': [3]}, {'ids': [1, 2]}) == {'ids': [1, 2]}

    def test_transform_with_priority_drops_the_other_list(self) -> None:
        assert attribute_map.transform({'ids': [1, 2]}, {'ids': [3]}, True) is None

    def test_transform_without_priority_keeps_the_other_list(self) -> None:
        assert attribute_map.transform({'ids': [1, 2]}, {'ids': [3]}, False) == {'ids': [3]}


class TestTransform:
    left = {'bold': True, 'color': 'red', 'font': None}
    right = {'color': 'blue', 'font': 'serif', 'italic': True}

    def test_left_is_undefined(self) -> None:
        assert attribute_map.transform(None, self.left, False) == self.left

    def test_right_is_undefined(self) -> None:
        assert attribute_map.transform(self.left, None, False) is None

    def test_both_are_undefined(self) -> None:
        assert attribute_map.transform(None, None, False) is None

    def test_with_priority(self) -> None:
        assert attribute_map.transform(self.left, self.right, True) == {'italic': True}

    def test_without_priority(self) -> None:
        assert attribute_map.transform(self.left, self.right, False) == self.right


def nest(levels: int, leaf: AttributeMap) -> AttributeMap:
    out: AttributeMap = leaf
    for _ in range(levels):
        out = {'n': out}
    return out


class TestComposeRecursionDepth:
    a = {'x': {'y': {'keep': 1}}}
    b = {'x': {'y': {'other': 2}}}

    def test_merges_every_level_by_default(self) -> None:
        assert attribute_map.compose(self.a, self.b) == {'x': {'y': {'keep': 1, 'other': 2}}}

    def test_lets_the_right_side_win_whole_once_the_depth_budget_runs_out(self) -> None:
        assert attribute_map.compose(self.a, self.b, False, 2) == {'x': {'y': {'other': 2}}}

    def test_never_recurses_at_a_depth_of_one(self) -> None:
        assert attribute_map.compose(self.a, self.b, False, 1) == {'x': {'y': {'other': 2}}}

    def test_gracefully_handles_circular_references_in_attribute_maps(self) -> None:
        a: AttributeMap = {'x': 1}
        b: AttributeMap = {'y': 1}
        a['b'] = b
        b['a'] = a
        composed = attribute_map.compose(a, b, False)
        # Asserted key by key rather than against a literal: comparing two distinct
        # self-referential dicts with `==` recurses forever in Python.
        assert composed is not None
        assert sorted(composed) == ['a', 'b', 'x', 'y']
        assert composed['x'] == 1
        assert composed['y'] == 1
        assert composed['b'] is b  # taken from `a`, which the right side does not mention
        assert composed['a'] is not a  # cloned out of the right side
        assert sorted(composed['a']) == ['b', 'x']

    def test_terminates_on_nesting_deeper_than_the_budget(self) -> None:
        assert (
            attribute_map.compose(nest(50, {'bold': True}), nest(50, {'italic': True}), False, 5)
            is not None
        )


class TestDiffRecursionDepth:
    a = {'x': {'y': {'same': 1, 'gone': 2}}}
    b = {'x': {'y': {'same': 1}}}

    def test_diffs_every_level_by_default(self) -> None:
        assert attribute_map.diff(self.a, self.b) == {'x': {'y': {'gone': None}}}

    def test_yields_the_whole_subtree_once_the_depth_budget_runs_out(self) -> None:
        assert attribute_map.diff(self.a, self.b, 2) == {'x': {'y': {'same': 1}}}


class TestInvertRecursionDepth:
    attr = {'x': {'y': {'a': 2, 'b': 3}}}
    base = {'x': {'y': {'a': 1}}}

    def test_inverts_every_level_by_default(self) -> None:
        assert attribute_map.invert(self.attr, self.base) == {'x': {'y': {'a': 1, 'b': None}}}

    def test_restores_the_whole_base_subtree_once_the_depth_budget_runs_out(self) -> None:
        assert attribute_map.invert(self.attr, self.base, 2) == {'x': {'y': {'a': 1}}}

    def test_terminates_on_nesting_deeper_than_the_budget(self) -> None:
        assert (
            attribute_map.invert(nest(50, {'bold': True}), nest(50, {'italic': True}), 5)
            is not None
        )


class TestTransformRecursionDepth:
    a = {'x': {'y': {'p': 1}}}
    b = {'x': {'y': {'q': 2}}}

    def test_transforms_every_level_by_default(self) -> None:
        assert attribute_map.transform(self.a, self.b, True) == {'x': {'y': {'q': 2}}}

    def test_drops_the_other_subtree_once_the_depth_budget_runs_out(self) -> None:
        assert attribute_map.transform(self.a, self.b, True, 2) is None

    def test_a_budget_matching_the_nesting_behaves_like_no_budget(self) -> None:
        assert attribute_map.transform(self.a, self.b, True, 3) == {'x': {'y': {'q': 2}}}

    def test_returns_the_other_side_untouched_without_priority(self) -> None:
        assert attribute_map.transform(self.a, self.b, False, 1) is self.b

    def test_returns_the_other_side_untouched_without_priority_arguments_flipped(self) -> None:
        assert attribute_map.transform(self.b, self.a, False, 1) is self.a

    def test_transforms_every_level_with_the_arguments_flipped(self) -> None:
        assert attribute_map.transform(self.b, self.a, True) == {'x': {'y': {'p': 1}}}

    def test_drops_the_other_subtree_with_the_arguments_flipped(self) -> None:
        assert attribute_map.transform(self.b, self.a, True, 2) is None

    def test_keeps_shallow_siblings_of_a_subtree_the_budget_cut_off(self) -> None:
        left = {'deep': {'y': {'p': 1}}}
        right = {'deep': {'y': {'q': 2}}, 'extra': True}
        assert attribute_map.transform(left, right, True) == {
            'deep': {'y': {'q': 2}},
            'extra': True,
        }
        assert attribute_map.transform(left, right, True, 2) == {'extra': True}


class TestTransformOverlappingNestedKeys:
    left = {'x': {'y': {'shared': 'left', 'onlyLeft': 1}}}
    right = {'x': {'y': {'shared': 'right', 'onlyRight': 2}}}

    def test_keeps_only_the_other_side_exclusive_keys(self) -> None:
        assert attribute_map.transform(self.left, self.right, True) == {
            'x': {'y': {'onlyRight': 2}}
        }

    def test_keeps_the_opposite_exclusive_keys_with_the_arguments_flipped(self) -> None:
        assert attribute_map.transform(self.right, self.left, True) == {'x': {'y': {'onlyLeft': 1}}}

    def test_drops_both_directions_once_the_depth_budget_runs_out(self) -> None:
        assert attribute_map.transform(self.left, self.right, True, 2) is None
        assert attribute_map.transform(self.right, self.left, True, 2) is None

    def test_is_unaffected_by_the_budget_without_priority(self) -> None:
        assert attribute_map.transform(self.left, self.right, False, 2) is self.right
        assert attribute_map.transform(self.right, self.left, False, 2) is self.left


class TestProtoKey:
    """Python has no prototype pollution, but `__proto__` keys are still ignored.

    The TypeScript implementation filters them so an attribute map arriving over the wire
    cannot reach `Object.prototype`; the filter is part of the format, so a delta composed
    in Python agrees with one composed in JavaScript about which keys exist.
    """

    @staticmethod
    def evil() -> AttributeMap:
        return json.loads('{"__proto__": {"polluted": true}}')

    @staticmethod
    def nested_evil() -> AttributeMap:
        return json.loads('{"outer": {"__proto__": {"polluted": true}}}')

    def test_compose_does_not_surface_injected_keys_as_attributes_of_the_result(self) -> None:
        composed = attribute_map.compose({'outer': {'bold': True}}, self.nested_evil())
        assert composed is not None
        assert list(composed) == ['outer']
        assert list(composed['outer']) == ['bold']

    def test_compose_ignores_a_top_level_proto_attribute_entirely(self) -> None:
        composed = attribute_map.compose({'bold': True}, self.evil())
        assert composed == {'bold': True}

    def test_compose_ignores_a_top_level_proto_attribute_on_the_left(self) -> None:
        composed = attribute_map.compose(self.evil(), {'bold': True})
        assert composed == {'bold': True}

    def test_compose_ignores_a_nested_proto_when_both_sides_nest_it(self) -> None:
        composed = attribute_map.compose(self.nested_evil(), self.nested_evil())
        assert composed is None

    def test_compose_copies_an_untouched_subtree_wholesale(self) -> None:
        # Only the keys compose walks are filtered; a subtree the other side does not
        # mention is copied as is, exactly as structuredClone does in TypeScript.
        composed = attribute_map.compose({'bold': True}, self.nested_evil())
        assert composed is not None
        assert composed['outer'] == {'__proto__': {'polluted': True}}

    def test_diff_ignores_a_nested_proto_on_either_side(self) -> None:
        assert attribute_map.diff({'outer': {'bold': True}}, self.nested_evil()) == {
            'outer': {'bold': None}
        }
        assert attribute_map.diff(self.nested_evil(), {'outer': {'bold': True}}) == {
            'outer': {'bold': True}
        }

    def test_diff_ignores_a_top_level_proto(self) -> None:
        assert attribute_map.diff({'bold': True}, self.evil()) == {'bold': None}
