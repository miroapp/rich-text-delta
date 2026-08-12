# Rich Text Delta (Python)

Python implementation of [Rich Text Delta](https://github.com/miroapp/rich-text-delta), a
fork of [`quill-delta`](https://github.com/quilljs/delta) with support for **nested
attribute maps** — attribute values may themselves be maps, and `compose`, `diff`,
`invert` and `transform` recurse into them instead of treating them as scalar values.

This is a port of the TypeScript implementation in
[`languages/typescript`](../typescript); the two agree operation for operation. The delta
format itself, and the full API reference, are documented in the
[root README](../../README.md).

## Install

Not on PyPI yet — install from the repository:

```sh
pip install "rich-text-delta @ git+https://github.com/miroapp/rich-text-delta#subdirectory=languages/python"
```

No runtime dependencies. Requires Python 3.9+.

```python
from rich_text_delta import Delta
```

## Usage

Build a document:

```python
doc = Delta().insert('Hello ').insert('World', {'bold': True}).insert('\n')
# [ {'insert': 'Hello '},
#   {'insert': 'World', 'attributes': {'bold': True}},
#   {'insert': '\n'} ]
```

Apply a change with `compose`:

```python
change = Delta().retain(6).retain(5, {'italic': True})

doc.compose(change)
# [ {'insert': 'Hello '},
#   {'insert': 'World', 'attributes': {'italic': True, 'bold': True}},
#   {'insert': '\n'} ]
```

Undo it with `invert`, which produces the change that reverses `change` against `doc`:

```python
undo = change.invert(doc)
# [ {'retain': 6}, {'retain': 5, 'attributes': {'italic': None}} ]

doc.compose(change).compose(undo) == doc  # True
```

Reconcile concurrent edits with `transform`. Given two changes made against the same
document, `a.transform(b, priority)` rewrites `b` so it can be applied after `a`:

```python
a = Delta().insert('A')
b = Delta().insert('B')

a.transform(b, True)  # [ {'retain': 1}, {'insert': 'B'} ]
```

### Nested attributes

Map-valued attributes are merged key by key rather than replaced wholesale:

```python
base = Delta().insert('x', {'style': {'color': 'red', 'size': 12}})
change = Delta().retain(1, {'style': {'color': 'blue'}})

base.compose(change)
# [ {'insert': 'x', 'attributes': {'style': {'color': 'blue', 'size': 12}}} ]
```

## Differences from the TypeScript API

The port follows the TypeScript source line for line. What differs is spelling and the
handful of places where JavaScript has no Python equivalent:

| TypeScript | Python |
| --- | --- |
| `delta.eachLine`, `changeLength`, `transformPosition`, `forEach` | `each_line`, `change_length`, `transform_position`, `for_each` |
| `Delta.registerEmbed` / `unregisterEmbed` | `Delta.register_embed` / `unregister_embed` |
| `namespace Op` / `namespace AttributeMap` | modules `rich_text_delta.op` / `rich_text_delta.attribute_map` (so `Op.length(op)` is `op.length(op)`) |
| `null` attribute value (a removal) | `None` |
| `undefined` (absent) | key missing from the map |
| `Infinity` | `math.inf` |
| `new Error(...)` | `ValueError` |
| string length in UTF-16 code units | string length in code points, so an emoji has length 1, not 2 |
| `delta.diff(other, {oldRange, newRange})` | the same camelCase keys, since they are part of the wire format |
| `structuredClone` | `copy.deepcopy` |
| `isEqual` from `es-toolkit` | an internal `deep_equal` with JavaScript's type rules |

Callbacks are called with every argument the TypeScript signature declares:
`filter`, `for_each` and `map` receive `(op, index)`, `reduce` receives
`(accumulator, op, index)`, `each_line` receives `(line, attributes, index)` and
`partition` receives `(op)`.

Embed handlers are any object with `compose(a, b, keep_null)`, `invert(a, b)` and
`transform(a, b, priority)` methods — see the `EmbedHandler` protocol.

Two Deltas compare equal when their ops do (`a == b`), which is what the TypeScript tests
express as `toEqual`. Defining `__eq__` makes `Delta` unhashable, as a mutable value type
should be.

The character diff behind `Delta.diff` is a vendored port of
[fast-diff](https://github.com/jhchen/fast-diff), so the package has no runtime
dependencies.

## Develop

Uses [uv](https://docs.astral.sh/uv/). From the repository root, `just` recipes suffixed
`-py` cover everything (`just test-py`, `just ci-py`, ...). Directly:

```sh
uv sync                # create .venv from uv.lock
uv run pytest          # run the tests
uv run ruff check .    # lint
uv run ruff format .   # format in place
uv run mypy            # type check
```

Tests live in `tests/` and mirror the TypeScript suite in
`languages/typescript/src/__tests__/` file for file — every case carries over except the
prototype-pollution ones that assert `Object.prototype` was left alone, which have no
meaning for Python dicts. The `__proto__` key is still filtered out of attribute maps, and
the cases covering that are ported.

## License

BSD-3-Clause. See [LICENSE](./LICENSE) and [NOTICE.txt](./NOTICE.txt). Derived from
[quill-delta](https://github.com/quilljs/delta) by Jason Chen. Bundles a port of
[fast-diff](https://github.com/jhchen/fast-diff) (Apache-2.0) as
`rich_text_delta/_fast_diff.py`.
