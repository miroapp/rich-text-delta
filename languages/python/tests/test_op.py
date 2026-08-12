# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from rich_text_delta import op


class TestLength:
    def test_delete(self) -> None:
        assert op.length({'delete': 5}) == 5

    def test_retain(self) -> None:
        assert op.length({'retain': 2}) == 2

    def test_insert_text(self) -> None:
        assert op.length({'insert': 'text'}) == 4

    def test_insert_embed(self) -> None:
        assert op.length({'insert': {'embed': 2}}) == 1
