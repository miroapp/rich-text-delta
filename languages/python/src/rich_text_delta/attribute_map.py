# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""Attribute maps and the four operations that combine them.

Attribute values may themselves be maps; ``compose``, ``diff``, ``invert`` and
``transform`` recurse into them up to ``MAX_RECURSION_DEPTH`` levels instead of treating
them as scalars. A value of ``None`` is a removal ("null" on the wire); a key that is
absent is simply unmentioned.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from ._js import UNDEFINED, deep_equal, prop

AttributeMap = Dict[str, Any]

MAX_RECURSION_DEPTH = 100


def _is_nested_map(value: Any) -> bool:
    return isinstance(value, dict)


def _safe_keys(map_: AttributeMap) -> List[str]:
    return [key for key in map_ if key != '__proto__']


def compose(
    a: Optional[AttributeMap] = None,
    b: Optional[AttributeMap] = None,
    keep_null: bool = False,
    depth: int = MAX_RECURSION_DEPTH,
) -> Optional[AttributeMap]:
    """Apply ``b`` on top of ``a``, returning ``None`` when nothing is left.

    Unless ``keep_null``, keys whose value is ``None`` are dropped rather than recorded as
    removals.
    """
    if not isinstance(a, dict):
        a = {}
    if not isinstance(b, dict):
        b = {}
    attributes = deepcopy(b)
    if not keep_null:
        attributes = {
            key: attributes[key] for key in _safe_keys(attributes) if attributes[key] is not None
        }
    for key in _safe_keys(a):
        if _is_nested_map(a.get(key)) and _is_nested_map(b.get(key)) and depth > 1:
            nested_composed = compose(a[key], b[key], keep_null, depth - 1)
            if nested_composed is None:
                attributes.pop(key, None)
            else:
                attributes[key] = nested_composed
        elif prop(a, key) is not UNDEFINED and prop(b, key) is UNDEFINED:
            attributes[key] = a[key]
    return attributes if len(attributes) > 0 else None


def diff(
    a: Optional[AttributeMap] = None,
    b: Optional[AttributeMap] = None,
    depth: int = MAX_RECURSION_DEPTH,
) -> Optional[AttributeMap]:
    """The change that turns ``a`` into ``b``, or ``None`` when they already match."""
    if not isinstance(a, dict):
        a = {}
    if not isinstance(b, dict):
        b = {}
    attrs: AttributeMap = {}
    for key in _safe_keys(a) + _safe_keys(b):
        if not deep_equal(prop(a, key), prop(b, key)):
            if _is_nested_map(a.get(key)) and _is_nested_map(b.get(key)) and depth > 1:
                nested_diff = diff(a[key], b[key], depth - 1)
                if nested_diff is not None:
                    attrs[key] = nested_diff
            else:
                attrs[key] = None if prop(b, key) is UNDEFINED else b[key]
    return attrs if len(attrs) > 0 else None


def invert(
    attr: Optional[AttributeMap] = None,
    base: Optional[AttributeMap] = None,
    depth: int = MAX_RECURSION_DEPTH,
) -> AttributeMap:
    """The change that undoes ``attr`` when it was applied to ``base``."""
    if attr is None:
        attr = {}
    if base is None:
        base = {}
    base_inverted: AttributeMap = {}
    for key in _safe_keys(base):
        if not deep_equal(prop(base, key), prop(attr, key)) and prop(attr, key) is not UNDEFINED:
            if _is_nested_map(base.get(key)) and _is_nested_map(attr.get(key)) and depth > 1:
                nested = invert(attr[key], base[key], depth - 1)
                if len(nested) > 0:
                    base_inverted[key] = nested
            else:
                base_inverted[key] = base[key]
    memo = base_inverted
    for key in _safe_keys(attr):
        if not deep_equal(prop(attr, key), prop(base, key)) and prop(base, key) is UNDEFINED:
            memo[key] = None
    return memo


def transform(
    a: Optional[AttributeMap],
    b: Optional[AttributeMap],
    priority: bool = False,
    depth: int = MAX_RECURSION_DEPTH,
) -> Optional[AttributeMap]:
    """Rewrite ``b`` so it can be applied after ``a``.

    Without ``priority``, ``b`` wins outright and is returned unchanged.
    """
    if not isinstance(a, dict):
        return b
    if not isinstance(b, dict):
        return None
    if not priority:
        return b  # b is unchanged when a doesn't have priority
    attributes: AttributeMap = {}
    for key in _safe_keys(b):
        if _is_nested_map(a.get(key)) and _is_nested_map(b.get(key)) and depth > 1:
            attr = transform(a[key], b[key], priority, depth - 1)
            if attr is not None:
                attributes[key] = attr
        elif prop(a, key) is UNDEFINED:
            attributes[key] = b[key]  # None is a valid value
    return attributes if len(attributes) > 0 else None
