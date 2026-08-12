# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""Walk a list of ops, splitting them at arbitrary offsets."""

from __future__ import annotations

import math
from typing import Any, List, Optional, Union, cast

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

    def has_next(self) -> bool:
        return self.peek_length() < math.inf

    def next(self, length: Optional[Union[int, float]] = None) -> Op:
        if not length:
            length = math.inf
        next_op = at(self.ops, self.index)
        if next_op is not UNDEFINED:
            offset = self.offset
            op_length = op_module.length(next_op)
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
                    ret_op['insert'] = next_op['insert'][offset : offset + length]
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
            return op_module.length(current) - self.offset
        else:
            return math.inf

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
