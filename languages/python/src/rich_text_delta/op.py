# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""A single operation, and how much of a document it covers."""

from __future__ import annotations

from typing import Any, Dict, TypedDict, Union

from . import _utf16
from ._js import is_number, is_object
from .attribute_map import AttributeMap


class Op(TypedDict, total=False):
    """Only one property out of ``insert``, ``delete`` and ``retain`` will be present."""

    insert: Union[str, Dict[str, Any]]
    delete: Union[int, float]
    retain: Union[int, float, Dict[str, Any]]

    attributes: AttributeMap


def length(op: Op) -> Union[int, float]:
    """How many UTF-16 code units of a document the operation covers.

    Embeds count as one, and an astral character as two.
    """
    if is_number(op.get('delete')):
        return op['delete']
    elif is_number(op.get('retain')):
        return op['retain']  # type: ignore[return-value]
    elif is_object(op.get('retain')):
        return 1
    else:
        insert = op.get('insert')
        return _utf16.length(insert) if isinstance(insert, str) else 1
