# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from typing import Any, Dict, Iterator, List

import pytest

from rich_text_delta import Delta, Op


class DeltaEmbedHandler:
    """The `delta` embed the TypeScript tests register: a payload of nested ops."""

    def compose(self, a: List[Op], b: List[Op], keep_null: bool) -> List[Op]:
        return Delta(a).compose(Delta(b)).ops

    def transform(self, a: List[Op], b: List[Op], priority: bool) -> List[Op]:
        transformed = Delta(a).transform(Delta(b), priority)
        assert isinstance(transformed, Delta)
        return transformed.ops

    def invert(self, a: List[Op], b: List[Op]) -> List[Op]:
        return Delta(a).invert(Delta(b)).ops


@pytest.fixture
def delta_embed() -> Iterator[None]:
    Delta.register_embed('delta', DeltaEmbedHandler())
    yield
    Delta.unregister_embed('delta')


def transform_delta(a: Delta, b: Delta, priority: bool = False) -> Delta:
    """`a.transform(b, priority)`, narrowed to the Delta overload."""
    transformed = a.transform(b, priority)
    assert isinstance(transformed, Delta)
    return transformed


def attributes_of(op: Op) -> Dict[str, Any]:
    attributes = op.get('attributes')
    assert isinstance(attributes, dict)
    return attributes
