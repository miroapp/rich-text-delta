# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""Walk a list of ops, splitting them at arbitrary offsets."""

from __future__ import annotations

import math
from typing import Any, List, Optional, Union, cast

from . import _utf16
from . import op as op_module
from ._js import UNDEFINED, at, is_number, is_object, is_truthy
from .op import Op


class OpIterator:
    ops: List[Op]
    index: int
    offset: int

    def __init__(self, ops: List[Op]) -> None:
        self.ops = ops
        self.index = 0
        self.offset = 0
        self._measured: Optional[str] = None
        self._units: bytes = b''

    def _code_units(self, text: str) -> bytes:
        """``text`` as code units, kept for as long as the iterator measures the same string.

        ``next`` and ``peek_length`` measure the current op several times per iteration of the
        compose and transform loops, and encoding is proportional to the length of the text.
        The cache is keyed on the string object rather than on ``index``, so it survives
        ``rest``'s index restore and an op being replaced invalidates it rather than being
        measured stale. Nothing in the package mutates a list an iterator is walking.
        """
        if text is not self._measured:
            self._measured = text
            self._units = _utf16.units(text)
        return self._units

    def _length(self, op: Op) -> Union[int, float]:
        """``op_module.length``, measuring insert text through the cache.

        Only text needs measuring; every other kind of op carries its own length. Delegating
        for anything but a plain text insert keeps ``op_module.length``'s precedence, which
        differs only for a malformed op holding more than one of the three keys.
        """
        insert = op.get('insert')
        if isinstance(insert, str) and 'delete' not in op and 'retain' not in op:
            return len(self._code_units(insert)) // 2
        return op_module.length(op)

    def has_next(self) -> bool:
        return self.peek_length() < math.inf

    def next(self, length: Optional[Union[int, float]] = None) -> Op:
        if not length:
            length = math.inf
        next_op = at(self.ops, self.index)
        if next_op is not UNDEFINED:
            offset = self.offset
            op_length = self._length(next_op)
            if length >= op_length - offset:
                length = op_length - offset
                self.index += 1
                self.offset = 0
            else:
                # `length` is below the remaining op length here, so it is a real offset
                self.offset += cast(int, length)
            if is_number(next_op.get('delete')):
                return {'delete': length}
            else:
                ret_op: Op = {}
                if is_truthy(next_op.get('attributes')):
                    ret_op['attributes'] = next_op['attributes']
                if is_number(next_op.get('retain')):
                    ret_op['retain'] = length
                elif is_object(next_op.get('retain')):
                    # offset should === 0, length should === 1
                    ret_op['retain'] = next_op['retain']
                elif isinstance(next_op.get('insert'), str):
                    insert = cast(str, next_op['insert'])
                    end = cast(int, offset + length)
                    ret_op['insert'] = _utf16.slice_units(self._code_units(insert), offset, end)
                else:
                    # offset should === 0, length should === 1
                    ret_op['insert'] = next_op.get('insert')
                return ret_op
        else:
            return {'retain': math.inf}

    def peek(self) -> Any:
        """The op at the current index, or ``UNDEFINED`` past the end."""
        return at(self.ops, self.index)

    def peek_length(self) -> Union[int, float]:
        current = at(self.ops, self.index)
        if current is not UNDEFINED:
            # Should never return 0 if our index is being managed correctly
            return self._length(current) - self.offset
        else:
            return math.inf

    def find_in_current(self, needle: str) -> int:
        """Where ``needle`` next appears in the current op's text, relative to the offset.

        ``thisOp.insert.indexOf(newline, start) - start`` upstream, where ``start`` is the
        offset. Asking the iterator instead reuses its measurement of the current op, rather
        than encoding the whole op again for every line. ``-1`` when the op holds no text or
        the needle is not there, which is the negative the caller tests for either way.
        """
        current = at(self.ops, self.index)
        insert = current.get('insert') if current is not UNDEFINED else None
        if not isinstance(insert, str):
            return -1
        found = _utf16.find_units(self._code_units(insert), _utf16.units(needle), self.offset)
        return found - self.offset if found >= 0 else -1

    def peek_type(self) -> str:
        current = at(self.ops, self.index)
        if current is not UNDEFINED:
            if is_number(current.get('delete')):
                return 'delete'
            elif is_number(current.get('retain')) or is_object(current.get('retain')):
                return 'retain'
            else:
                return 'insert'
        return 'retain'

    def rest(self) -> List[Op]:
        if not self.has_next():
            return []
        elif self.offset == 0:
            return self.ops[self.index :]
        else:
            offset = self.offset
            index = self.index
            next_op = self.next()
            rest = self.ops[self.index :]
            self.offset = offset
            self.index = index
            return [next_op] + rest
