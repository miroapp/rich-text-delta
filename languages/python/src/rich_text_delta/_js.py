# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""JavaScript semantics this port depends on.

The TypeScript source leans on a handful of JavaScript behaviours that have no direct
Python equivalent: truthiness of objects, ``typeof``, the ``undefined``/``null`` split
and ``es-toolkit``'s ``isEqual``. Reproducing them here keeps the ported modules a
line-for-line reading of the originals.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence, TypeVar


class _Undefined:
    """Stand-in for JavaScript's ``undefined``, distinct from ``null`` (``None``)."""

    _instance: _Undefined | None = None

    def __new__(cls) -> _Undefined:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return 'undefined'

    def __bool__(self) -> bool:
        return False


UNDEFINED = _Undefined()
"""A missing property, as opposed to a property whose value is ``null``."""


def prop(obj: Mapping[str, Any], key: str) -> Any:
    """``obj[key]`` in JavaScript: a missing key reads as ``undefined``, not ``None``."""
    if key in obj:
        return obj[key]
    return UNDEFINED


def js_typeof(value: Any) -> str:
    """``typeof value``. Note ``typeof None`` is ``'object'``, matching ``typeof null``."""
    if value is UNDEFINED:
        return 'undefined'
    if value is None:
        return 'object'
    if isinstance(value, bool):
        return 'boolean'
    if isinstance(value, (int, float)):
        return 'number'
    if isinstance(value, str):
        return 'string'
    if callable(value):
        return 'function'
    return 'object'


def is_number(value: Any) -> bool:
    """``typeof value === 'number'``. Python bools are ints; JavaScript booleans are not."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_object(value: Any) -> bool:
    """``typeof value === 'object' && value !== null``."""
    return isinstance(value, (dict, list))


def is_truthy(value: Any) -> bool:
    """JavaScript truthiness. Notably ``{}`` and ``[]`` are truthy; ``0`` and ``''`` are not."""
    if value is UNDEFINED or value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, (int, float)):
        return value != 0 and not math.isnan(value)
    if isinstance(value, str):
        return value != ''
    return True


def deep_equal(a: Any, b: Any) -> bool:
    """``isEqual`` from ``es-toolkit``: deep value equality with JavaScript's type rules.

    Unlike ``==``, booleans are never equal to numbers and ``undefined`` is never equal
    to ``None``.
    """
    if a is b:
        return True
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if a is None or b is None or a is UNDEFINED or b is UNDEFINED:
        return False
    if is_number(a) and is_number(b):
        return a == b
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        if len(a) != len(b):
            return False
        return all(key in b and deep_equal(value, b[key]) for key, value in a.items())
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return False
        return all(deep_equal(x, y) for x, y in zip(a, b))
    if type(a) is not type(b):
        return False
    return bool(a == b)


T = TypeVar('T')


def at(items: Sequence[T], index: int) -> Any:
    """``items[index]`` in JavaScript: out of range reads as ``undefined``, never wraps."""
    if 0 <= index < len(items):
        return items[index]
    return UNDEFINED
