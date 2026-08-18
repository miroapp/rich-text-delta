# Language-agnostic test cases

A corpus of test cases for implementations of the Delta format, so that a port in
another language can be checked against the same expectations as the reference
TypeScript implementation in this repository. The test cases express delta values as
the typical json serialization of deltas, which is an array of ops.

## Layout

Every `*.yaml` file under this directory, at any depth, is a case file.

A file that yields no cases should be treated as a failure rather than skipped,
so that a misnamed or unparsed file cannot silently contribute nothing. The
reference harness asserts each file is non-empty.

## Case format

Each file has a top-level `tests` array. A case looks like this:

```yaml
- name: insert + retain
  method: Delta.compose
  args:
    receiver: '[{"insert":"A"}]'
    other: '[{"retain":1,"attributes":{"bold":true}]'
  expected: '[{"insert":"A","attributes":{"bold":true}}]'
```

### Encoding: YAML envelope, JSON values

YAML carries structure, case names and comments. **Every value is a JSON string**,
parsed as JSON after the YAML is parsed. This is deliberate, not incidental:

- Attribute maps use keys like `"1"`, `"2"`, `"99"`. In JSON, object keys are
  always strings. In YAML, `1:` is an *integer* key, so a port using a YAML
  library would get `{1: true}` where the reference has `{"1": true}`.
- YAML 1.1 parsers (SnakeYAML, PyYAML) resolve bare `no`, `yes`, `on`, `off` to
  booleans; YAML 1.2 parsers treat them as strings. An attribute value of `no`
  would silently differ between ports.

Confining values to JSON removes both hazards. The exceptions are arguments whose
type is fixed by the schema and cannot be coerced ambiguously — `priority`,
`keepNull`, `depth`, `index`, `start`, `end`, `length`, `maxInserted`,
`maxDeleted` — which are written as native YAML booleans and integers, or omitted.

### `method`

Fully qualified, because `compose`, `diff`, `invert` and `transform` exist on both
`Delta` and `AttributeMap` with different signatures and different semantics.

| method | arguments |
| --- | --- |
| `Delta.compose` | `receiver` (document or change), `other` |
| `Delta.transform` | `receiver` (change), `other`, `priority` |
| `Delta.transformPosition` | `receiver` (change), `index`, `priority` |
| `Delta.invert` | `receiver` (change), `base` (document) |
| `Delta.diff` | `receiver` (document), `other` (document) |
| `Delta.concat` | `receiver`, `other` |
| `Delta.chop` | `receiver` |
| `Delta.slice` | `receiver`, `start`, `end` |
| `Delta.length` | `receiver` |
| `Delta.build` | `calls` |
| `AttributeMap.compose` | `a`, `b`, `keepNull`, `depth` |
| `AttributeMap.diff` | `a`, `b`, `depth` |
| `AttributeMap.invert` | `attr`, `base`, `depth` |
| `AttributeMap.transform` | `a`, `b`, `priority`, `depth` |
| `Op.length` | `op` |

Arguments are named, and each language implementation needs to specify a harness that
determines how to call these functions according to the syntax and api structure in that
language.

OOP languages that implement these functions as instance methods should use the 
`receiver` argument as "this" in test cases. Note that `Delta.invert` takes an
argument named `base`, which is a *document*, unlike `other` elsewhere.

### `Delta.build`

Construction and op normalisation are tested through a pseudo-method whose only
argument is a sequence of builder calls:

```yaml
- name: insert(text) after delete
  method: Delta.build
  args:
    calls:
      - op: delete
        args: { length: 1 }
      - op: insert
        args: { arg: '"a"' }
  expected: '[{"insert":"a"},{"delete":1}]'
```

Calls run in order against a fresh, empty delta. The available ops are `insert`
(`arg`, optional `attributes`), `retain` (`arg`, optional `attributes`), `delete`
(`length`), and `push` (`op`).

`insert` and `retain` take an overloaded first argument — text or an embed for
`insert`, a length or an embed for `retain` — named `arg` in both cases, because
the wire format does not discriminate either: `{"insert":"a"}` and
`{"insert":{"embed":1}}` share a key. The type follows from the parsed JSON.

Because `attributes` is JSON, `attributes: 'null'` and `attributes: '{}'` are
distinguishable from omitting it, which matters: several cases exist precisely to
show all three are equivalent in their effect.

### Expectation forms

Exactly one of `expected`, `error` or `invariant` is present.

**`expected: '<json>'`** — the operation's result, compared structurally.

**`expected: null`** — the operation returned nothing. Distinct from returning an
empty map: `AttributeMap.compose`, `diff` and `transform` return nothing when the
result would be empty, whereas `invert` returns `{}`. In a port this is the
difference between `null`/`nil`/`None` and an empty map. Note that `null` *inside*
a JSON value means something different — an attribute removal — but no operation
in this corpus ever returns a bare null, so the two never collide.

**`error: { kind: ... }`** — the operation throws. Only the kind is asserted, not
a message: the reference messages interpolate JavaScript's `typeof` operator
(`cannot retain a string`), which no other language can reproduce. Ports map
their own exception types onto these four kinds:

| kind | when |
| --- | --- |
| `cannot-retain-non-embed` | retaining an embed against text or a number |
| `embed-types-mismatch` | composing or transforming two different embed types |
| `no-embed-handler` | an embed type with no registered handler |
| `diff-non-document` | `diff` called with an operand that is not a document |

**`invariant: composes-to-other`** — used only by `Delta.diff`, together with
`maxInserted` and `maxDeleted`. See below.

### `embeds`

A case that needs a registered embed handler declares it:

```yaml
embeds: { delta: nested-delta }
```

The key is the embed type; the value names a handler the port must implement.
Declaring it per case keeps cases hermetic — any case can run alone, in any
order, with no ambient setup — and it makes non-registration expressible, which
`no-embed-handler` cases depend on.

There is currently one named handler, **`nested-delta`**. Its value is an ops
array, and its three operations recurse into `Delta` itself:

```
compose(a, b, keepNull) = Delta(a).compose(Delta(b)).ops
transform(a, b, priority) = Delta(a).transform(Delta(b), priority).ops
invert(a, b) = Delta(a).invert(Delta(b)).ops
```

`keepNull` is ignored. Because the definition is self-referential, a port can
implement it with no user-supplied logic.

## Equality

Results are compared **structurally, strictly**:

- Objects are unordered key-to-value maps. Key order never matters.
- Arrays are ordered. Attribute values that are arrays are atomic — never merged
  element-wise, last write wins.
- Numbers compare by mathematical value, not representation. A port whose JSON
  parser yields `1.0` or `float64(1)` where the reference has `1` passes.
- **An absent key is not equal to a key holding an empty map.** The reference
  never emits `attributes: {}` or `attributes: null` — it sets the key only when
  the map is non-empty — so a port that emits empty attribute maps produces JSON
  that will not compare equal on the wire, and fails here. Omitting the key when
  the map is empty is a normalisation rule ports must implement.
- Keys whose value is `undefined` are not representable on the wire and are not
  considered present.

## `Delta.diff`

`diff` is the one operation whose exact output is not required to match.

The reference decomposes text changes with diff-match-patch (Myers 1986 plus
Neil Fraser's cleanup heuristics). A port using any other diff library can
produce a different but equally valid edit script for the same inputs — the
library's own documentation shows two different correct answers for `'aaa'` to
`'aaaa'` depending on cursor position. Requiring the reference's decomposition
would mean requiring a specific 1986 algorithm and one library's heuristics.

So diff cases assert:

1. **`composes-to-other`** — `receiver.compose(receiver.diff(other))` equals
   `other`. This is the property that actually matters.
2. **An edit-size ceiling** — the result inserts at most `maxInserted` characters
   and deletes at most `maxDeleted`. Without this the invariant is vacuous: a
   `diff` that deletes the whole document and reinserts the target satisfies it
   for every input.

The ceiling is portable because edit *size* is canonical even when the edit
*script* is not. For any minimal script, `inserted - deleted` equals
`len(other) - len(receiver)` and `inserted + deleted` equals the edit distance,
which pins both numbers. The recorded ceilings are the reference's own counts, and
cleanup heuristics can only inflate them above the true minimum, so `<=` is the
right comparison. Embeds count as one character; text is counted in UTF-16 code
units.

Attribute-only diffs — where both documents have identical text — involve no text
decomposition, so their results are fully determined and the ceiling is `0`/`0`.

**One diff case asserts exact ops instead**: `nested attributes with the value
null are not ignored by diff`. There the invariant is false, and correctly so —
`other` holds an attribute whose value is `null`, which is a removal instruction
rather than document content, so composing the diff back strips it and cannot
reproduce `other`. Since both sides have identical text, exact ops are fully
portable for that case.

## Case identity

There are no id fields. A case is identified by its file and its `name`, and names
are unique within a file. The reference harness enforces uniqueness. Names are not
unique *across* files, and several are deliberately reused.

