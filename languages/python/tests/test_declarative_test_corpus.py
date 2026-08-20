# Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
# SPDX-License-Identifier: BSD-3-Clause

"""The language-agnostic corpus in `json-test-cases/`, run against this port."""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, Iterator, List, Optional, Pattern, Tuple

import pytest
import yaml

from rich_text_delta import Delta, Op, attribute_map
from rich_text_delta import op as op_module

CORPUS_ROOT = Path(__file__).resolve().parents[3] / 'declarative-test-corpus'

# --- corpus format -------------------------------------------------------

ParamType = str  # 'delta' | 'attrs' | 'op' | 'bool' | 'int' | 'calls'

TestCase = Dict[str, Any]


@dataclass(frozen=True)
class Param:
    name: str
    type: ParamType


@dataclass(frozen=True)
class MethodSpec:
    """Every argument the method takes, receiver included, and how to call it.

    Only the argument names are part of the corpus; keyword dispatch is this port's
    calling convention.
    """

    params: List[Param]
    invoke: Callable[[Dict[str, Any]], Any]


#: JSON-encoded values in the YAML, decoded before dispatch.
JSON_TYPES: FrozenSet[ParamType] = frozenset({'delta', 'attrs', 'op'})

#: An instance method's receiver is an ordinary argument named `receiver`.
RECEIVER = Param('receiver', 'delta')

#: Types with no meaningful absent value, so leaving one out — whether by omitting the
#: key or writing `null` — is an authoring error rather than a case. `bool` and `int`
#: arguments all have defaults, and an absent `attrs` argument is itself under test.
REQUIRED_TYPES: FrozenSet[ParamType] = frozenset({'delta', 'op', 'calls'})


def _kwargs(args: Dict[str, Any], **mapping: str) -> Dict[str, Any]:
    """The supplied arguments, renamed to this port's parameter names.

    Arguments the case leaves out are omitted rather than passed as `None`, so the
    implementation's own defaults apply.
    """
    return {py_name: args[name] for name, py_name in mapping.items() if name in args}


def _as_delta(value: Any) -> Delta:
    """`Delta.transform`'s Delta overload, narrowed."""
    assert isinstance(value, Delta)
    return value


METHODS: Dict[str, MethodSpec] = {
    'Delta.compose': MethodSpec(
        params=[RECEIVER, Param('other', 'delta')],
        invoke=lambda args: args['receiver'].compose(args['other']).ops,
    ),
    'Delta.transform': MethodSpec(
        params=[RECEIVER, Param('other', 'delta'), Param('priority', 'bool')],
        invoke=lambda args: (
            _as_delta(
                args['receiver'].transform(args['other'], **_kwargs(args, priority='priority'))
            ).ops
        ),
    ),
    'Delta.transformPosition': MethodSpec(
        params=[RECEIVER, Param('index', 'int'), Param('priority', 'bool')],
        invoke=lambda args: args['receiver'].transform_position(
            **_kwargs(args, index='index', priority='priority')
        ),
    ),
    'Delta.invert': MethodSpec(
        params=[RECEIVER, Param('base', 'delta')],
        invoke=lambda args: args['receiver'].invert(args['base']).ops,
    ),
    'Delta.diff': MethodSpec(
        params=[RECEIVER, Param('other', 'delta')],
        invoke=lambda args: args['receiver'].diff(args['other']).ops,
    ),
    'Delta.concat': MethodSpec(
        params=[RECEIVER, Param('other', 'delta')],
        invoke=lambda args: args['receiver'].concat(args['other']).ops,
    ),
    'Delta.chop': MethodSpec(
        params=[RECEIVER],
        invoke=lambda args: args['receiver'].chop().ops,
    ),
    'Delta.slice': MethodSpec(
        params=[RECEIVER, Param('start', 'int'), Param('end', 'int')],
        invoke=lambda args: args['receiver'].slice(**_kwargs(args, start='start', end='end')).ops,
    ),
    'Delta.length': MethodSpec(
        params=[RECEIVER],
        invoke=lambda args: args['receiver'].length(),
    ),
    'Delta.build': MethodSpec(
        params=[Param('calls', 'calls')],
        invoke=lambda args: _build(args['calls']).ops,
    ),
    'AttributeMap.compose': MethodSpec(
        params=[
            Param('a', 'attrs'),
            Param('b', 'attrs'),
            Param('keepNull', 'bool'),
            Param('depth', 'int'),
        ],
        invoke=lambda args: attribute_map.compose(
            args.get('a'), args.get('b'), **_kwargs(args, keepNull='keep_null', depth='depth')
        ),
    ),
    'AttributeMap.diff': MethodSpec(
        params=[Param('a', 'attrs'), Param('b', 'attrs'), Param('depth', 'int')],
        invoke=lambda args: attribute_map.diff(
            args.get('a'), args.get('b'), **_kwargs(args, depth='depth')
        ),
    ),
    'AttributeMap.invert': MethodSpec(
        params=[Param('attr', 'attrs'), Param('base', 'attrs'), Param('depth', 'int')],
        invoke=lambda args: attribute_map.invert(
            args.get('attr'), args.get('base'), **_kwargs(args, depth='depth')
        ),
    ),
    'AttributeMap.transform': MethodSpec(
        params=[
            Param('a', 'attrs'),
            Param('b', 'attrs'),
            Param('priority', 'bool'),
            Param('depth', 'int'),
        ],
        invoke=lambda args: attribute_map.transform(
            args.get('a'), args.get('b'), **_kwargs(args, priority='priority', depth='depth')
        ),
    ),
    'Op.length': MethodSpec(
        params=[Param('op', 'op')],
        invoke=lambda args: op_module.length(args['op']),
    ),
}


class NestedDeltaHandler:
    """An embed whose value is an ops array, combined by recursing into Delta itself.

    Self-referential, so every port can implement it without any user-supplied logic.
    """

    def compose(self, a: List[Op], b: List[Op], keep_null: bool) -> List[Op]:
        return Delta(a).compose(Delta(b)).ops

    def transform(self, a: List[Op], b: List[Op], priority: bool) -> List[Op]:
        return _as_delta(Delta(a).transform(Delta(b), priority)).ops

    def invert(self, a: List[Op], b: List[Op]) -> List[Op]:
        return Delta(a).invert(Delta(b)).ops


#: Named embed handlers a case may request via `embeds`.
EMBED_HANDLERS: Dict[str, NestedDeltaHandler] = {'nested-delta': NestedDeltaHandler()}

#: Maps this implementation's error messages onto the corpus error kinds.
ERROR_KINDS: List[Tuple[Pattern[str], str]] = [
    (re.compile(r'^cannot retain a '), 'cannot-retain-non-embed'),
    (re.compile(r'^embed types not matched: '), 'embed-types-mismatch'),
    (re.compile(r'^no handlers for embed type '), 'no-embed-handler'),
    (re.compile(r'^diff\(\) called (on|with) non-document$'), 'diff-non-document'),
]

INVARIANTS = ('composes-to-other',)

# --- loading -------------------------------------------------------------


def _case_files() -> List[Path]:
    return sorted(path for path in CORPUS_ROOT.rglob('*') if path.suffix in ('.yaml', '.yml'))


def _load(path: Path) -> List[TestCase]:
    parsed = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    return parsed.get('tests') or []


def _rel(path: Path) -> str:
    return str(path.relative_to(CORPUS_ROOT))


def _params() -> List[Any]:
    return [
        pytest.param(path, case, id=f'{_rel(path)}: {case.get("name")}')
        for path in _FILES
        for case in _load(path)
    ]


_FILES = _case_files()

# --- dispatch ------------------------------------------------------------


def _build(calls: List[Dict[str, Any]]) -> Delta:
    delta = Delta()
    for call in calls:
        args = call.get('args') or {}
        attributes = json.loads(args['attributes']) if 'attributes' in args else None
        kind = call['op']
        if kind == 'insert':
            delta.insert(json.loads(args['arg']), attributes)
        elif kind == 'retain':
            delta.retain(json.loads(args['arg']), attributes)
        elif kind == 'delete':
            delta.delete(args['length'])
        elif kind == 'push':
            delta.push(json.loads(args['op']))
        else:
            raise AssertionError(f'unknown builder op: {kind}')
    return delta


def _decode(param_type: ParamType, raw: Any) -> Any:
    if param_type not in JSON_TYPES:
        return raw
    value = json.loads(raw)
    return Delta(value) if param_type == 'delta' else value


def _supplied(case: TestCase, name: str) -> bool:
    """Whether the case supplies an argument.

    A `null` counts as not supplied, so the implementation's default applies — which is
    how the reference treats an argument left out. `attributes.yaml` spells out every
    argument and writes `null` for the ones it does not supply, rather than omitting the
    key; both spellings mean the same thing here. Unrelated to a `null` *inside* a JSON
    value, which is an attribute removal.
    """
    args = case.get('args') or {}
    return name in args and args[name] is not None


def _decoded_args(spec: MethodSpec, case: TestCase) -> Dict[str, Any]:
    args = case.get('args') or {}
    return {
        param.name: _decode(param.type, args[param.name])
        for param in spec.params
        if _supplied(case, param.name)
    }


def _structural(value: Any) -> Any:
    """Strict structural form: objects are unordered key->value maps, arrays are ordered,
    numbers compare by value, and an absent key is NOT equal to one holding an empty map.

    Booleans are tagged so they never compare equal to `0`/`1`, which Python would
    otherwise accept.
    """
    if isinstance(value, bool):
        return ('bool', value)
    if isinstance(value, (int, float)):
        return ('number', float(value))
    if isinstance(value, dict):
        return {key: _structural(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_structural(item) for item in value]
    return value


def _classify(error: BaseException) -> str:
    message = str(error)
    for pattern, kind in ERROR_KINDS:
        if pattern.search(message):
            return kind
    raise AssertionError(f'unclassified error, no corpus kind matches: {message}')


def _edit_size(ops: List[Op]) -> Tuple[float, float]:
    inserted: float = 0
    deleted: float = 0
    for op in ops:
        insert = op.get('insert')
        if insert is not None:
            # UTF-16 code units, matching the reference harness's `op.insert.length`. Spelled
            # out rather than taken from `_utf16`, so the ceiling does not lean on the code
            # under test.
            inserted += (
                len(insert.encode('utf-16-le', 'surrogatepass')) // 2
                if isinstance(insert, str)
                else 1
            )
        delete = op.get('delete')
        if isinstance(delete, (int, float)) and not isinstance(delete, bool):
            deleted += delete
    return inserted, deleted


# --- validation ----------------------------------------------------------


def _validate(path: Path, case: TestCase) -> MethodSpec:
    where = f'{_rel(path)} :: {case.get("name")}'
    assert case.get('name'), f'{_rel(path)}: a case is missing `name`'

    spec = METHODS.get(case.get('method', ''))
    assert spec is not None, f'{where}: unknown method `{case.get("method")}`'

    allowed = {param.name for param in spec.params}
    for key in case.get('args') or {}:
        assert key in allowed, f'{where}: `{case["method"]}` has no argument `{key}`'
    for param in spec.params:
        if param.type in REQUIRED_TYPES:
            assert _supplied(case, param.name), (
                f'{where}: `{case["method"]}` requires argument `{param.name}`'
            )

    forms = [
        'expected' in case,
        case.get('error') is not None,
        case.get('invariant') is not None,
    ]
    assert sum(forms) == 1, f'{where}: expected exactly one of `expected`, `error`, `invariant`'

    error = case.get('error')
    if error is not None:
        kinds = [kind for _, kind in ERROR_KINDS]
        assert error['kind'] in kinds, f'{where}: unknown error kind `{error["kind"]}`'
    invariant = case.get('invariant')
    if invariant is not None:
        assert invariant in INVARIANTS, f'{where}: unknown invariant `{invariant}`'
    for embed_type, handler in (case.get('embeds') or {}).items():
        assert handler in EMBED_HANDLERS, f'{where}: unknown embed handler `{handler}`'
        assert isinstance(embed_type, str)

    return spec


# --- execution -----------------------------------------------------------


@contextmanager
def _registered(case: TestCase) -> Iterator[None]:
    """The embed handlers the case declares, registered for its duration only."""
    embeds: Dict[str, str] = case.get('embeds') or {}
    for embed_type, handler in embeds.items():
        Delta.register_embed(embed_type, EMBED_HANDLERS[handler])
    try:
        yield
    finally:
        for embed_type in embeds:
            Delta.unregister_embed(embed_type)


def _check(where: str, case: TestCase, spec: MethodSpec) -> None:
    args = _decoded_args(spec, case)

    error = case.get('error')
    if error is not None:
        try:
            spec.invoke(args)
        except Exception as thrown:
            assert _classify(thrown) == error['kind'], where
            return
        pytest.fail(f'{where}: expected a thrown error')

    actual = spec.invoke(args)

    if case.get('invariant') is not None:
        # `diff` decomposition is algorithm-dependent, so the corpus asserts that
        # applying the result reproduces the target document, plus a ceiling on edit
        # size so a degenerate delete-all-and-reinsert cannot pass.
        result = Delta(actual)
        applied = Delta(json.loads(case['args']['receiver'])).compose(result).ops
        assert _structural(applied) == _structural(json.loads(case['args']['other'])), (
            f'{where}: applying the diff must reproduce `other`'
        )
        inserted, deleted = _edit_size(result.ops)
        assert inserted <= case['maxInserted'], f'{where}: inserted characters'
        assert deleted <= case['maxDeleted'], f'{where}: deleted characters'
        return

    expected: Optional[str] = case['expected']
    if expected is None:
        assert actual is None, f'{where}: expected no result'
        return

    assert _structural(actual) == _structural(json.loads(expected)), where


def test_corpus_is_discovered() -> None:
    assert _FILES, f'no case files under {CORPUS_ROOT}'


@pytest.mark.parametrize('path', _FILES, ids=[_rel(path) for path in _FILES])
def test_file_is_non_empty(path: Path) -> None:
    cases = _load(path)
    assert len(cases) > 0
    names = [case.get('name') for case in cases]
    assert len(set(names)) == len(names), f'{_rel(path)}: duplicate case name within the file'


@pytest.mark.parametrize(('path', 'case'), _params())
def test_case(path: Path, case: TestCase) -> None:
    spec = _validate(path, case)
    with _registered(case):
        _check(f'{_rel(path)} :: {case["name"]}', case, spec)
