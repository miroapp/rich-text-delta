# Copyright (c) 2022, Slab, Inc.
# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""Deltas: documents, and changes to documents."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from . import _fast_diff
from . import attribute_map as attribute_map_module
from . import op as op_module
from ._js import UNDEFINED, at, deep_equal, is_number, is_object, is_truthy, js_typeof, prop
from .attribute_map import AttributeMap
from .op import Op
from .op_iterator import OpIterator

NULL_CHARACTER = chr(0)  # Placeholder char for embed in diff()

T = TypeVar('T')
R = TypeVar('R')


class EmbedHandler(Protocol[T]):
    """How to combine the payloads of a registered embed type."""

    def compose(self, a: T, b: T, keep_null: bool) -> T: ...

    def invert(self, a: T, b: T) -> T: ...

    def transform(self, a: T, b: T, priority: bool) -> T: ...


def _get_embed_type_and_data(a: Any, b: Any) -> Tuple[str, Any, Any]:
    if js_typeof(a) != 'object' or a is None:
        raise ValueError(f'cannot retain a {js_typeof(a)}')
    if js_typeof(b) != 'object' or b is None:
        raise ValueError(f'cannot retain a {js_typeof(b)}')
    embed_type = next(iter(a), None)
    b_type = next(iter(b), None)
    if not embed_type or embed_type != b_type:
        raise ValueError(f'embed types not matched: {_js_str(embed_type)} != {_js_str(b_type)}')
    return embed_type, a[embed_type], b[embed_type]


def _js_str(value: Any) -> str:
    """String interpolation of a possibly missing key, as JavaScript would print it."""
    return 'undefined' if value is None else str(value)


class Delta:
    """An ordered list of operations describing a document or a change to one."""

    _handlers: Dict[str, EmbedHandler[Any]] = {}

    @classmethod
    def register_embed(cls, embed_type: str, handler: EmbedHandler[T]) -> None:
        cls._handlers[embed_type] = handler

    @classmethod
    def unregister_embed(cls, embed_type: str) -> None:
        cls._handlers.pop(embed_type, None)

    @classmethod
    def _get_handler(cls, embed_type: str) -> EmbedHandler[Any]:
        handler = cls._handlers.get(embed_type)
        if not handler:
            raise ValueError(f'no handlers for embed type "{_js_str(embed_type)}"')
        return handler

    ops: List[Op]

    def __init__(self, ops: Optional[Union[List[Op], Dict[str, Any], Delta]] = None) -> None:
        # Assume we are given a well formed ops
        if isinstance(ops, list):
            self.ops = ops
        elif isinstance(ops, Delta) and isinstance(ops.ops, list):
            self.ops = ops.ops
        elif isinstance(ops, dict) and isinstance(ops.get('ops'), list):
            self.ops = ops['ops']
        else:
            self.ops = []

    def insert(
        self,
        arg: Union[str, Dict[str, Any]],
        attributes: Optional[AttributeMap] = None,
    ) -> Delta:
        new_op: Op = {}
        if isinstance(arg, str) and len(arg) == 0:
            return self
        new_op['insert'] = arg
        if attributes is not None and isinstance(attributes, dict) and len(attributes) > 0:
            new_op['attributes'] = attributes
        return self.push(new_op)

    def delete(self, length: Union[int, float]) -> Delta:
        if length <= 0:
            return self
        return self.push({'delete': length})

    def retain(
        self,
        length: Union[int, float, Dict[str, Any]],
        attributes: Optional[AttributeMap] = None,
    ) -> Delta:
        if is_number(length) and length <= 0:  # type: ignore[operator]
            return self
        new_op: Op = {'retain': length}
        if attributes is not None and isinstance(attributes, dict) and len(attributes) > 0:
            new_op['attributes'] = attributes
        return self.push(new_op)

    def push(self, new_op: Op) -> Delta:
        index = len(self.ops)
        last_op = at(self.ops, index - 1)
        new_op = deepcopy(new_op)
        if js_typeof(last_op) == 'object':
            if is_number(new_op.get('delete')) and is_number(last_op.get('delete')):
                self.ops[index - 1] = {'delete': last_op['delete'] + new_op['delete']}
                return self
            # Since it does not matter if we insert before or after deleting at the same
            # index, always prefer to insert first
            if is_number(last_op.get('delete')) and new_op.get('insert') is not None:
                index -= 1
                last_op = at(self.ops, index - 1)
                if js_typeof(last_op) != 'object':
                    self.ops.insert(0, new_op)
                    return self
            if deep_equal(prop(new_op, 'attributes'), prop(last_op, 'attributes')):
                if isinstance(new_op.get('insert'), str) and isinstance(last_op.get('insert'), str):
                    self.ops[index - 1] = {'insert': last_op['insert'] + new_op['insert']}
                    if js_typeof(prop(new_op, 'attributes')) == 'object':
                        self.ops[index - 1]['attributes'] = new_op['attributes']
                    return self
                elif is_number(new_op.get('retain')) and is_number(last_op.get('retain')):
                    self.ops[index - 1] = {'retain': last_op['retain'] + new_op['retain']}
                    if js_typeof(prop(new_op, 'attributes')) == 'object':
                        self.ops[index - 1]['attributes'] = new_op['attributes']
                    return self
        if index == len(self.ops):
            self.ops.append(new_op)
        else:
            self.ops.insert(index, new_op)
        return self

    def chop(self) -> Delta:
        last_op = at(self.ops, len(self.ops) - 1)
        if (
            last_op is not UNDEFINED
            and is_number(last_op.get('retain'))
            and not is_truthy(last_op.get('attributes'))
        ):
            self.ops.pop()
        return self

    def filter(self, predicate: Callable[[Op, int], bool]) -> List[Op]:
        return [op for index, op in enumerate(self.ops) if predicate(op, index)]

    def for_each(self, predicate: Callable[[Op, int], Any]) -> None:
        for index, op in enumerate(self.ops):
            predicate(op, index)

    def map(self, predicate: Callable[[Op, int], R]) -> List[R]:
        return [predicate(op, index) for index, op in enumerate(self.ops)]

    def partition(self, predicate: Callable[[Op], bool]) -> Tuple[List[Op], List[Op]]:
        passed: List[Op] = []
        failed: List[Op] = []

        def collect(op: Op, _index: int) -> None:
            target = passed if predicate(op) else failed
            target.append(op)

        self.for_each(collect)
        return passed, failed

    def reduce(self, predicate: Callable[[R, Op, int], R], initial_value: R) -> R:
        accum = initial_value
        for index, op in enumerate(self.ops):
            accum = predicate(accum, op, index)
        return accum

    def change_length(self) -> Union[int, float]:
        def step(length: Union[int, float], elem: Op, _index: int) -> Union[int, float]:
            if is_truthy(elem.get('insert')):
                return length + op_module.length(elem)
            elif is_truthy(elem.get('delete')):
                return length - elem['delete']
            return length

        initial: Union[int, float] = 0
        return self.reduce(step, initial)

    def length(self) -> Union[int, float]:
        initial: Union[int, float] = 0
        return self.reduce(lambda length, elem, _index: length + op_module.length(elem), initial)

    def slice(self, start: Union[int, float] = 0, end: Union[int, float] = math.inf) -> Delta:
        ops = []
        iterator = OpIterator(self.ops)
        index: Union[int, float] = 0
        while index < end and iterator.has_next():
            if index < start:
                next_op = iterator.next(start - index)
            else:
                next_op = iterator.next(end - index)
                ops.append(next_op)
            index += op_module.length(next_op)
        return Delta(ops)

    def compose(self, other: Delta) -> Delta:
        this_iter = OpIterator(self.ops)
        other_iter = OpIterator(other.ops)
        ops: List[Op] = []
        first_other = other_iter.peek()
        if (
            first_other is not UNDEFINED
            and is_number(first_other.get('retain'))
            and first_other.get('attributes') is None
        ):
            first_left = first_other['retain']
            while this_iter.peek_type() == 'insert' and this_iter.peek_length() <= first_left:
                first_left -= this_iter.peek_length()
                ops.append(this_iter.next())
            if first_other['retain'] - first_left > 0:
                other_iter.next(first_other['retain'] - first_left)
        delta = Delta(ops)
        while this_iter.has_next() or other_iter.has_next():
            if other_iter.peek_type() == 'insert':
                delta.push(other_iter.next())
            elif this_iter.peek_type() == 'delete':
                delta.push(this_iter.next())
            else:
                length = min(this_iter.peek_length(), other_iter.peek_length())
                this_op = this_iter.next(length)
                other_op = other_iter.next(length)
                if is_truthy(other_op.get('retain')):
                    new_op: Op = {}
                    if is_number(this_op.get('retain')):
                        new_op['retain'] = (
                            length if is_number(other_op.get('retain')) else other_op['retain']
                        )
                    else:
                        if is_number(other_op.get('retain')):
                            if this_op.get('retain') is None:
                                new_op['insert'] = this_op['insert']
                            else:
                                new_op['retain'] = this_op['retain']
                        else:
                            action = 'insert' if this_op.get('retain') is None else 'retain'
                            embed_type, this_data, other_data = _get_embed_type_and_data(
                                prop(this_op, action),
                                other_op['retain'],
                            )
                            handler = Delta._get_handler(embed_type)
                            embed = {
                                embed_type: handler.compose(
                                    this_data, other_data, action == 'retain'
                                )
                            }
                            if action == 'retain':
                                new_op['retain'] = embed
                            else:
                                new_op['insert'] = embed
                    # Preserve null when composing with a retain, otherwise remove it for
                    # inserts
                    attributes = attribute_map_module.compose(
                        this_op.get('attributes'),
                        other_op.get('attributes'),
                        is_number(this_op.get('retain')),
                    )
                    if attributes:
                        new_op['attributes'] = attributes
                    delta.push(new_op)

                    # Optimization if rest of other is just retain
                    if not other_iter.has_next() and deep_equal(delta.ops[-1], new_op):
                        rest = Delta(this_iter.rest())
                        return delta.concat(rest).chop()

                    # Other op should be delete, we could be an insert or retain
                    # Insert + delete cancels out
                elif is_number(other_op.get('delete')) and (
                    is_number(this_op.get('retain')) or is_object(this_op.get('retain'))
                ):
                    delta.push(other_op)
        return delta.chop()

    def concat(self, other: Delta) -> Delta:
        delta = Delta(list(self.ops))
        if len(other.ops) > 0:
            delta.push(other.ops[0])
            delta.ops = delta.ops + other.ops[1:]
        return delta

    def diff(
        self,
        other: Delta,
        cursor: Optional[Union[int, Dict[str, Any]]] = None,
    ) -> Delta:
        if self.ops is other.ops:
            return Delta()
        strings = []
        for delta in (self, other):
            parts = []
            for op in delta.ops:
                if op.get('insert') is not None:
                    insert = op['insert']
                    parts.append(insert if isinstance(insert, str) else NULL_CHARACTER)
                else:
                    prep = 'on' if delta is other else 'with'
                    raise ValueError('diff() called ' + prep + ' non-document')
            strings.append(''.join(parts))
        ret_delta = Delta()
        diff_result = _fast_diff.diff(strings[0], strings[1], cursor, True)
        this_iter = OpIterator(self.ops)
        other_iter = OpIterator(other.ops)
        for component in diff_result:
            length: Union[int, float] = len(component[1])
            while length > 0:
                op_length: Union[int, float] = 0
                if component[0] == _fast_diff.INSERT:
                    op_length = min(other_iter.peek_length(), length)
                    ret_delta.push(other_iter.next(op_length))
                elif component[0] == _fast_diff.DELETE:
                    op_length = min(length, this_iter.peek_length())
                    this_iter.next(op_length)
                    ret_delta.delete(op_length)
                elif component[0] == _fast_diff.EQUAL:
                    op_length = min(this_iter.peek_length(), other_iter.peek_length(), length)
                    this_op = this_iter.next(op_length)
                    other_op = other_iter.next(op_length)
                    if deep_equal(prop(this_op, 'insert'), prop(other_op, 'insert')):
                        ret_delta.retain(
                            op_length,
                            attribute_map_module.diff(
                                this_op.get('attributes'), other_op.get('attributes')
                            ),
                        )
                    else:
                        ret_delta.push(other_op).delete(op_length)
                length -= op_length
        return ret_delta.chop()

    def each_line(
        self,
        predicate: Callable[[Delta, AttributeMap, int], Any],
        newline: str = '\n',
    ) -> None:
        iterator = OpIterator(self.ops)
        line = Delta()
        i = 0
        while iterator.has_next():
            if iterator.peek_type() != 'insert':
                return
            this_op = iterator.peek()
            start = cast(int, op_module.length(this_op) - iterator.peek_length())
            insert = this_op.get('insert')
            index = insert.find(newline, start) - start if isinstance(insert, str) else -1
            if index < 0:
                line.push(iterator.next())
            elif index > 0:
                line.push(iterator.next(index))
            else:
                if predicate(line, iterator.next(1).get('attributes') or {}, i) is False:
                    return
                i += 1
                line = Delta()
        if line.length() > 0:
            predicate(line, {}, i)

    def invert(self, base: Delta) -> Delta:
        inverted = Delta()

        def step(base_index: Union[int, float], op: Op, _index: int) -> Union[int, float]:
            if is_truthy(op.get('insert')):
                inverted.delete(op_module.length(op))
            elif is_number(op.get('retain')) and op.get('attributes') is None:
                retain = cast(Union[int, float], op['retain'])
                inverted.retain(retain)
                return base_index + retain
            elif is_truthy(op.get('delete')) or is_number(op.get('retain')):
                length = cast(
                    Union[int, float],
                    op['delete'] if is_truthy(op.get('delete')) else op['retain'],
                )
                sliced = base.slice(base_index, base_index + length)

                def invert_base_op(base_op: Op, _base_index: int) -> None:
                    if is_truthy(op.get('delete')):
                        inverted.push(base_op)
                    elif is_truthy(op.get('retain')) and is_truthy(op.get('attributes')):
                        inverted.retain(
                            op_module.length(base_op),
                            attribute_map_module.invert(
                                op.get('attributes'), base_op.get('attributes')
                            ),
                        )

                sliced.for_each(invert_base_op)
                return base_index + length
            elif is_object(op.get('retain')):
                sliced = base.slice(base_index, base_index + 1)
                base_op = OpIterator(sliced.ops).next()
                embed_type, op_data, base_op_data = _get_embed_type_and_data(
                    op['retain'], prop(base_op, 'insert')
                )
                handler = Delta._get_handler(embed_type)
                inverted.retain(
                    {embed_type: handler.invert(op_data, base_op_data)},
                    attribute_map_module.invert(op.get('attributes'), base_op.get('attributes')),
                )
                return base_index + 1
            return base_index

        initial: Union[int, float] = 0
        self.reduce(step, initial)
        return inverted.chop()

    def transform(
        self,
        arg: Union[int, float, Delta],
        priority: bool = False,
    ) -> Union[int, float, Delta]:
        """Rewrite ``arg`` — another delta, or an index — so it applies after this one."""
        priority = bool(priority)
        if is_number(arg):
            return self.transform_position(arg, priority)  # type: ignore[arg-type]
        other: Delta = arg  # type: ignore[assignment]
        this_iter = OpIterator(self.ops)
        other_iter = OpIterator(other.ops)
        delta = Delta()
        while this_iter.has_next() or other_iter.has_next():
            if this_iter.peek_type() == 'insert' and (
                priority or other_iter.peek_type() != 'insert'
            ):
                delta.retain(op_module.length(this_iter.next()))
            elif other_iter.peek_type() == 'insert':
                delta.push(other_iter.next())
            else:
                length = min(this_iter.peek_length(), other_iter.peek_length())
                this_op = this_iter.next(length)
                other_op = other_iter.next(length)
                if is_truthy(this_op.get('delete')):
                    # Our delete either makes their delete redundant or removes their retain
                    continue
                elif is_truthy(other_op.get('delete')):
                    delta.push(other_op)
                else:
                    this_data = this_op.get('retain')
                    other_data = other_op.get('retain')
                    transformed_data: Union[int, float, Dict[str, Any]] = (
                        cast(Dict[str, Any], other_data) if is_object(other_data) else length
                    )
                    if is_object(this_data) and is_object(other_data):
                        this_embed = cast(Dict[str, Any], this_data)
                        other_embed = cast(Dict[str, Any], other_data)
                        # An empty embed has no first key; JavaScript reads `undefined` here
                        # and `_get_handler` then throws, as it does upstream.
                        embed_type = cast(str, next(iter(this_embed), None))
                        if embed_type == next(iter(other_embed), None):
                            handler = Delta._get_handler(embed_type)
                            if handler:
                                transformed_data = {
                                    embed_type: handler.transform(
                                        this_embed[embed_type],
                                        other_embed[embed_type],
                                        priority,
                                    )
                                }

                    # We retain either their retain or insert
                    delta.retain(
                        transformed_data,
                        attribute_map_module.transform(
                            this_op.get('attributes'), other_op.get('attributes'), priority
                        ),
                    )
        return delta.chop()

    def transform_position(
        self, index: Union[int, float], priority: bool = False
    ) -> Union[int, float]:
        priority = bool(priority)
        this_iter = OpIterator(self.ops)
        offset: Union[int, float] = 0
        while this_iter.has_next() and offset <= index:
            length = this_iter.peek_length()
            next_type = this_iter.peek_type()
            this_iter.next()
            if next_type == 'delete':
                index -= min(length, index - offset)
                continue
            elif next_type == 'insert' and (offset < index or not priority):
                index += length
            offset += length
        return index

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Delta):
            return NotImplemented
        return deep_equal(self.ops, other.ops)

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self.ops!r})'


# Mirrors the TypeScript statics; a Python module is the closest thing to a TS namespace.
Delta.Op = op_module  # type: ignore[attr-defined]
Delta.OpIterator = OpIterator  # type: ignore[attr-defined]
Delta.AttributeMap = attribute_map_module  # type: ignore[attr-defined]
