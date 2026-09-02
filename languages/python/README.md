# Rich Text Delta (Python)

Python implementation of [Rich Text Delta](https://github.com/miroapp/rich-text-delta), a
fork of [`quill-delta`](https://github.com/quilljs/delta) with support for **nested
attribute maps** — attribute values may themselves be maps, and `compose`, `diff`,
`invert` and `transform` recurse into them instead of treating them as scalar values.

This is a port of the TypeScript implementation in
[`languages/typescript`](../typescript); the two agree operation for operation. The
[root README](../../README.md) introduces the delta format and covers the repository
itself.

## Install

```sh
pip install rich-text-delta
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

## API

Every method below mirrors the TypeScript API under a `snake_case` name; see
[Differences from the TypeScript API](#differences-from-the-typescript-api) for the full
list of spelling changes. An `Op` is a plain `dict`, and an attribute map is a plain
`dict` of `str` to anything.

#### Operations

- [`insert`](#insert-operation)
- [`delete`](#delete-operation)
- [`retain`](#retain-operation)

#### Construction

- [`constructor`](#constructor)
- [`insert`](#insert)
- [`delete`](#delete)
- [`retain`](#retain)

#### Documents

These methods called on or with non-document Deltas will result in undefined behavior.

- [`concat`](#concat)
- [`diff`](#diff)
- [`each_line`](#each_line)
- [`invert`](#invert)

#### Utility

- [`filter`](#filter)
- [`for_each`](#for_each)
- [`length`](#length)
- [`map`](#map)
- [`partition`](#partition)
- [`reduce`](#reduce)
- [`slice`](#slice)

#### Operational Transform

- [`compose`](#compose)
- [`transform`](#transform)
- [`transform_position`](#transform_position)


### Operations

#### Insert Operation

Insert operations have an `insert` key defined. A `str` value represents inserting text. Any other type represents inserting an embed (however only one level of dict comparison will be performed for equality).

In both cases of text and embeds, an optional `attributes` key can be defined with a dict to describe additional formatting information. Formats can be changed by the [retain](#retain) operation.

```python
# Insert a bolded "Text"
{'insert': 'Text', 'attributes': {'bold': True}}

# Insert a link
{'insert': 'Google', 'attributes': {'link': 'https://www.google.com'}}

# Insert an embed
{
    'insert': {'image': 'https://octodex.github.com/images/labtocat.png'},
    'attributes': {'alt': 'Lab Octocat'},
}

# Insert another embed
{
    'insert': {'video': 'https://www.youtube.com/watch?v=dMH0bHeiRNg'},
    'attributes': {
        'width': 420,
        'height': 315,
    },
}
```

#### Delete Operation

Delete operations have a numeric `delete` key defined representing the number of characters to delete. All embeds have a length of 1.

```python
# Delete the next 10 characters
{'delete': 10}
```

#### Retain Operation

Retain operations have a numeric `retain` key defined representing the number of characters to keep (other libraries might use the name keep or skip). An optional `attributes` key can be defined with a dict to describe formatting changes to the character range. A value of `None` in the `attributes` dict represents removal of that key.

*Note: It is not necessary to retain the last characters of a document as this is implied.*

```python
# Keep the next 5 characters
{'retain': 5}

# Keep and bold the next 5 characters
{'retain': 5, 'attributes': {'bold': True}}

# Keep and unbold the next 5 characters
# More specifically, remove the bold key in the attributes dict
# in the next 5 characters
{'retain': 5, 'attributes': {'bold': None}}
```

*Note: lengths are counted in UTF-16 code units — see [Text and UTF-16](#text-and-utf-16).*


### Construction

#### constructor

Creates a new Delta object.

##### Methods

- `Delta()`
- `Delta(ops)`
- `Delta(delta)`

##### Parameters

- `ops` - list of operations
- `delta` - a `Delta`, or a dict with an `ops` key set to a list of operations

*Note: No validity/sanity check is performed when constructed with ops or delta. The new delta's internal ops list will also be assigned from ops or delta.ops without deep copying.*

##### Example

```python
import json

delta = Delta([
    {'insert': 'Hello World'},
    {'insert': '!', 'attributes': {'bold': True}},
])

packet = json.dumps(delta.ops)

other = Delta(json.loads(packet))

chained = Delta().insert('Hello World').insert('!', {'bold': True})
```

---

#### insert()

Appends an insert operation. Returns `self` for chainability.

##### Methods

- `insert(text, attributes=None)`
- `insert(embed, attributes=None)`

##### Parameters

- `text` - `str` representing text to insert
- `embed` - dict representing embed type to insert
- `attributes` - Optional attributes to apply

##### Example

```python
delta.insert('Text', {'bold': True, 'color': '#ccc'})
delta.insert({'image': 'https://octodex.github.com/images/labtocat.png'})
```

---

#### delete()

Appends a delete operation. Returns `self` for chainability.

##### Methods

- `delete(length)`

##### Parameters

- `length` - Number of characters to delete

##### Example

```python
delta.delete(5)
```

---

#### retain()

Appends a retain operation. Returns `self` for chainability.

##### Methods

- `retain(length, attributes=None)`

##### Parameters

- `length` - Number of characters to retain
- `attributes` - Optional attributes to apply

##### Example

```python
delta.retain(4).retain(5, {'color': '#0c6'})
```

### Documents

#### concat()

Returns a new Delta representing the concatenation of this and another document Delta's operations.

##### Methods

- `concat(other)`

##### Parameters

- `other` - Document Delta to concatenate

##### Returns

- `Delta` - Concatenated document Delta

##### Example

```python
a = Delta().insert('Hello')
b = Delta().insert('!', {'bold': True})

concat = a.concat(b)
# Delta([{'insert': 'Hello'}, {'insert': '!', 'attributes': {'bold': True}}])
```

---

#### diff()

Returns a Delta representing the difference between two documents. Optionally, accepts a suggested index where change took place, often representing a cursor position *before* change.

##### Methods

- `diff(other)`
- `diff(other, cursor)`

##### Parameters

- `other` - Document Delta to diff against
- `cursor` - Suggested index where change took place, or a dict `{'oldRange': ..., 'newRange': ...}` where each range is `{'index': ..., 'length': ...}`. The keys stay camelCase because they are part of the wire format.

##### Returns

- `Delta` - difference between the two documents

##### Example

```python
a = Delta().insert('Hello')
b = Delta().insert('Hello!')

diff = a.diff(b)  # Delta([{'retain': 5}, {'insert': '!'}])
                  # a.compose(diff) == b
```

---

#### each_line()

Iterates through document Delta, calling a given function with a Delta and attributes dict, representing the line segment.

##### Methods

- `each_line(predicate, newline='\n')`

##### Parameters

- `predicate` - function to call on each line group, receiving `(line, attributes, index)`
- `newline` - newline character, defaults to `\n`

##### Example

```python
delta = (
    Delta()
    .insert('Hello\n\n')
    .insert('World')
    .insert({'image': 'octocat.png'})
    .insert('\n', {'align': 'right'})
    .insert('!')
)

def log(line, attributes, i):
    print(repr(line), attributes, i)
    # Can return False to exit loop early

delta.each_line(log)
# Should print:
# Delta([{'insert': 'Hello'}]) {} 0
# Delta([]) {} 1
# Delta([{'insert': 'World'}, {'insert': {'image': 'octocat.png'}}]) {'align': 'right'} 2
# Delta([{'insert': '!'}]) {} 3
```

---

#### invert()

Returns an inverted delta that has the opposite effect of against a base document delta. That is `base.compose(delta).compose(inverted) == base`.

##### Methods

- `invert(base)`

##### Parameters

- `base` - Document delta to invert against

##### Returns

- `Delta` - inverted delta against the base delta

##### Example

```python
base = Delta().insert('Hello\n').insert('World')
delta = Delta().retain(6, {'bold': True}).insert('!').delete(5)

inverted = delta.invert(base)
# Delta([{'retain': 6, 'attributes': {'bold': None}},
#        {'insert': 'World'},
#        {'delete': 1}])
# base.compose(delta).compose(inverted) == base
```


### Utility

#### filter()

Returns a list of operations that passes a given function.

##### Methods

- `filter(predicate)`

##### Parameters

- `predicate` - Function to test each operation against, receiving `(op, index)`. Return `True` to keep the operation, `False` otherwise.

##### Returns

- `list` - Filtered resulting list

##### Example

```python
delta = (
    Delta()
    .insert('Hello', {'bold': True})
    .insert({'image': 'https://octodex.github.com/images/labtocat.png'})
    .insert('World!')
)

text = ''.join(
    operation['insert']
    for operation in delta.filter(
        lambda operation, index: isinstance(operation.get('insert'), str)
    )
)
```

---

#### for_each()

Iterates through operations, calling the provided function for each operation.

##### Methods

- `for_each(predicate)`

##### Parameters

- `predicate` - Function to call during iteration, receiving `(op, index)`.

##### Example

```python
delta.for_each(lambda operation, index: print(operation))
```

---

#### length()

Returns length of a Delta, which is the sum of the lengths of its operations, in UTF-16 code units.

##### Methods

- `length()`

##### Example

```python
Delta().insert('Hello').length()  # Returns 5

Delta().insert('A').retain(2).delete(1).length()  # Returns 4
```

The length of a single operation is `op.length(operation)`, from the
`rich_text_delta.op` module.

---

#### map()

Returns a new list with the results of calling the provided function on each operation.

##### Methods

- `map(predicate)`

##### Parameters

- `predicate` - Function to call, receiving `(op, index)` and returning an element of the new list to be returned

##### Returns

- `list` - A new list with each element being the result of the given function.

##### Example

```python
delta = (
    Delta()
    .insert('Hello', {'bold': True})
    .insert({'image': 'https://octodex.github.com/images/labtocat.png'})
    .insert('World!')
)

text = ''.join(
    delta.map(
        lambda operation, index: operation['insert']
        if isinstance(operation.get('insert'), str)
        else ''
    )
)
```

---

#### partition()

Create a tuple of two lists, the first with operations that pass the given function, the other that failed.

##### Methods

- `partition(predicate)`

##### Parameters

- `predicate` - Function to call, receiving `(op)`, returning whether that operation passed

##### Returns

- `tuple` - A tuple of two lists, the first with passed operations, the other with failed operations

##### Example

```python
delta = (
    Delta()
    .insert('Hello', {'bold': True})
    .insert({'image': 'https://octodex.github.com/images/labtocat.png'})
    .insert('World!')
)

passed, failed = delta.partition(
    lambda operation: isinstance(operation.get('insert'), str)
)
# passed == [{'insert': 'Hello', 'attributes': {'bold': True}},
#            {'insert': 'World!'}]
# failed == [{'insert': {'image': 'https://octodex.github.com/images/labtocat.png'}}]
```

---

#### reduce()

Applies given function against an accumulator and each operation to reduce to a single value.

##### Methods

- `reduce(predicate, initial_value)`

##### Parameters

- `predicate` - Function to call per iteration, receiving `(accumulator, op, index)` and returning an accumulated value
- `initial_value` - Initial value to pass to the first call to predicate

##### Returns

- the accumulated value

##### Example

```python
from rich_text_delta import Delta, op

delta = (
    Delta()
    .insert('Hello', {'bold': True})
    .insert({'image': 'https://octodex.github.com/images/labtocat.png'})
    .insert('World!')
)

length = delta.reduce(
    lambda length, operation, index: length + op.length(operation), 0
)  # 12
```

---

#### slice()

Returns a copy of the delta with a subset of operations.

##### Methods

- `slice()`
- `slice(start)`
- `slice(start, end)`

##### Parameters

- `start` - Start index of subset, defaults to 0
- `end` - End index of subset, defaults to rest of operations (`math.inf`)

##### Example

```python
delta = Delta().insert('Hello', {'bold': True}).insert(' World')

copy = delta.slice()
# Delta([{'attributes': {'bold': True}, 'insert': 'Hello'}, {'insert': ' World'}])

world = delta.slice(6)  # Delta([{'insert': 'World'}])

space = delta.slice(5, 6)  # Delta([{'insert': ' '}])
```


### Operational Transform

#### compose()

Returns a Delta that is equivalent to applying the operations of own Delta, followed by another Delta.

##### Methods

- `compose(other)`

##### Parameters

- `other` - Delta to compose

##### Example

```python
a = Delta().insert('abc')
b = Delta().retain(1).delete(1)

composed = a.compose(b)  # composed == Delta().insert('ac')
```

---

#### transform()

Transform given Delta against own operations.

##### Methods

- `transform(other, priority=False)`
- `transform(index, priority=False)` - Alias for [`transform_position`](#transform_position)

##### Parameters

- `other` - Delta to transform
- `priority` - Boolean used to break ties. If `True`, then `self` takes priority over `other`, that is, its actions are considered to happen "first."

##### Returns

- `Delta` - transformed Delta

##### Example

```python
a = Delta().insert('a')
b = Delta().insert('b').retain(5).insert('c')

a.transform(b, True)   # Delta().retain(1).insert('b').retain(5).insert('c')
a.transform(b, False)  # Delta().insert('b').retain(6).insert('c')
```

---

#### transform_position()

Transform an index against the delta. Useful for representing cursor/selection positions.

##### Methods

- `transform_position(index, priority=False)`

##### Parameters

- `index` - index to transform

##### Returns

- the transformed index

##### Example

```python
delta = Delta().retain(5).insert('a')
delta.transform_position(4)  # 4
delta.transform_position(5)  # 6
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

## Text and UTF-16

Text is measured and indexed in **UTF-16 code units**, as the reference implementation and the
wire format are: `op.length({'insert': '😀'})` is 2, not 1. So are `Delta.length`,
`change_length`, the lengths given to `delete` and `retain`, the bounds of `slice`, the index
`transform_position` takes and returns, every `retain` and `delete` count in an emitted op, and
the `cursor` / `oldRange` / `newRange` indices of `diff`. A character outside the Basic
Multilingual Plane — an emoji, a flag, an astral CJK ideograph — spans two of them, so
`len(op['insert'])` is *not* the op's length for such text; `op.length(op)` is.

Insert text is an ordinary `str`, kept maximally composed, so `op['insert']` reads as text:

```python
>>> Delta().insert('a😀b').length()
4
>>> Delta().insert('a😀b').ops
[{'insert': 'a😀b'}]
```

A boundary landing **inside** a surrogate pair splits it, yielding a lone surrogate on each
side, exactly as the reference does:

```python
>>> Delta().insert('😀').slice(0, 1).ops
[{'insert': '\ud83d'}]
```

That string is well-formed UTF-16 but not valid Unicode. The halves reassemble into the
character as soon as they are adjacent again — when `push` merges two ops, through `concat`, or
on a JSON round-trip — so a lone surrogate only survives while the two sides really are apart.

Serializing is safe by default: `json.dumps` escapes a lone surrogate as `\ud83d`, and
`json.loads` reads it back, so ops round-trip through JSON exactly. Two things to know:

- `json.dumps(ops, ensure_ascii=False).encode('utf-8')` **raises** `UnicodeEncodeError` on a
  lone surrogate. Pass `errors='surrogatepass'` if you need that path, and be aware the bytes it
  produces are not strict UTF-8 and many decoders will reject them.
- `print(op['insert'])` hits the same problem on a UTF-8 stream. `repr()` is safe.

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
