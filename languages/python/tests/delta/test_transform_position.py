# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from rich_text_delta import Delta


def test_insert_before_position() -> None:
    delta = Delta().insert('A')
    assert delta.transform(2) == 3


def test_insert_after_position() -> None:
    delta = Delta().retain(2).insert('A')
    assert delta.transform(1) == 1


def test_insert_at_position() -> None:
    delta = Delta().retain(2).insert('A')
    assert delta.transform(2, True) == 2
    assert delta.transform(2, False) == 3


def test_delete_before_position() -> None:
    delta = Delta().delete(2)
    assert delta.transform(4) == 2


def test_delete_after_position() -> None:
    delta = Delta().retain(4).delete(2)
    assert delta.transform(2) == 2


def test_delete_across_position() -> None:
    delta = Delta().retain(1).delete(4)
    assert delta.transform(2) == 1


def test_insert_and_delete_before_position() -> None:
    delta = Delta().retain(2).insert('A').delete(2)
    assert delta.transform(4) == 3


def test_insert_before_and_delete_across_position() -> None:
    delta = Delta().retain(2).insert('A').delete(4)
    assert delta.transform(4) == 3


def test_delete_before_and_delete_across_position() -> None:
    delta = Delta().delete(1).retain(1).delete(4)
    assert delta.transform(4) == 1
