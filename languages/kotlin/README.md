# Rich Text Delta (Kotlin)

Kotlin/JVM implementation of [Rich Text Delta](https://github.com/miroapp/rich-text-delta), a
fork of [`quill-delta`](https://github.com/quilljs/delta) with support for **nested
attribute maps**. An attribute value may itself be a map, and `compose`, `diff`, `invert`
and `transform` recurse into it rather than treating it as a scalar.

This is a port of the TypeScript implementation in
[`languages/typescript`](../typescript). It is checked against the same
[declarative test corpus](../../declarative-test-corpus). The
[root README](../../README.md) introduces the delta format and covers the repository
itself.

## Install

```kotlin
dependencies {
    implementation("com.miro:rich-text-delta:5.2.0")
}
```

Needs Java 17 or later. Runtime dependencies:
- [kotlinx.serialization](https://github.com/Kotlin/kotlinx.serialization) JSON, which is part of the public API.
- [diff-match-patch](https://github.com/google/diff-match-patch), used by `diff`.

```kotlin
import com.miro.richtextdelta.Delta
```

## Usage

Build a document:

```kotlin
val doc = Delta().insert("Hello ").insert("World", mapOf("bold" to true)).insert("\n")
// [{"insert":"Hello "},{"insert":"World","attributes":{"bold":true}},{"insert":"\n"}]
```

Apply a change with `compose`:

```kotlin
val change = Delta().retain(6).retain(5, mapOf("italic" to true))

doc.compose(change)
// [{"insert":"Hello "},{"insert":"World","attributes":{"italic":true,"bold":true}},{"insert":"\n"}]
```

Undo it with `invert`, which produces the change that reverses `change` against `doc`:

```kotlin
val undo = change.invert(doc)
// [{"retain":6},{"retain":5,"attributes":{"italic":null}}]

doc.compose(change).compose(undo) == doc // true
```

Reconcile concurrent edits with `transform`. Given two changes made against the same
document, `a.transform(b, priority)` rewrites `b` so it can be applied after `a`:

```kotlin
val a = Delta().insert("A")
val b = Delta().insert("B")

a.transform(b, true) // [{"retain":1},{"insert":"B"}]
```

Compute the change between two documents with `diff`:

```kotlin
Delta().insert("Hello").diff(Delta().insert("Hello!")) // [{"retain":5},{"insert":"!"}]
```

### Nested attributes

Map-valued attributes are merged key by key rather than replaced wholesale:

```kotlin
val base = Delta().insert("x", mapOf("style" to mapOf("color" to "red", "size" to 12)))
val change = Delta().retain(1, mapOf("style" to mapOf("color" to "blue")))

base.compose(change)
// [{"insert":"x","attributes":{"style":{"color":"blue","size":12}}}]
```

### JSON

Deltas and ops read and write the standard wire format:

```kotlin
val delta = Delta.fromJson("""[{"insert":"Hi","attributes":{"bold":true}},{"insert":{"image":"cat.png"}}]""")
delta.toJson()          // the same JSON back
delta.toJsonElement()   // as a kotlinx.serialization JsonArray

Json.encodeToString(delta)              // Delta and Op are @Serializable
Json.decodeFromString<Delta>("""[{"retain":3}]""")
```

`Delta.fromJson` accepts either an array of ops or an object `{"ops": [...]}`. `Op.fromJson` /
`op.toJson()` and `AttributeMaps.fromJson` / `AttributeMaps.toJson` do the same job for single
ops and attribute maps. JSON only: the serializers reject any other format.

## Data model

```kotlin
typealias AttributeMap = Map<String, Any?>

sealed interface Op {
    val attributes: AttributeMap?
    data class Insert(val value: InsertValue) : Op
    data class Retain(val value: RetainValue) : Op
    data class Delete(val length: Int) : Op
    fun length(): Int
}

sealed interface InsertValue          // InsertText(text, attributes) | InsertEmbed(embed, attributes)
sealed interface RetainValue          // RetainLength(length, attributes) | RetainEmbed(embed, attributes)
```

Pattern-match ops with `when`:

```kotlin
when (op) {
    is Op.Insert -> when (val value = op.value) {
        is InsertText -> value.text
        is InsertEmbed -> value.embed
    }
    is Op.Retain -> op.value // RetainLength or RetainEmbed
    is Op.Delete -> op.length
}
```

- **Attribute values** are plain Kotlin values: `Map<String, Any?>`, `List<Any?>`, `String`,
  `Boolean`, numbers and `null`. That is also what `fromJson` produces; integers come back as
  `Int` where they fit, then `Long`, then `Double`. Numbers compare by value, so `1` and `1L`
  and `1.0` are the same attribute value.
- **A key mapped to `null` is a removal**, for example `mapOf("bold" to null)`. A key that is
  absent is simply not set. `attributes = null` on an op means it has none. An op whose
  attributes are an empty map keeps them, as the TypeScript implementation does. The
  `insert`/`retain` builders treat `null` and `emptyMap()` as no attributes.
- **An embed** is any non-text value. By convention it is a map with a single key, the embed
  type, such as `mapOf("image" to "cat.png")`. Only map embeds can be retained against other
  embeds through an [embed handler](#embeds). `InsertEmbed` rejects a `String` and
  `RetainEmbed` rejects a `Number`, because those are text and lengths.

## API

| | |
| --- | --- |
| Construction | `Delta(ops)`, `insert(text, attributes)`, `insert(embed, attributes)`, `delete(length)`, `retain(length, attributes)`, `retain(embed, attributes)`, `push(op)`, `chop()` |
| Documents | `concat(other)`, `diff(other)`, `eachLine(newline) { line, attributes, index -> Boolean }`, `invert(base)` |
| Utility | `ops`, `filter`, `forEach`, `map`, `partition`, `reduce(initial) { acc, op, index -> }`, `length()`, `changeLength()`, `slice(start, end)` |
| Operational transform | `compose(other)`, `transform(other, priority)`, `transform(index, priority)`, `transformPosition(index, priority)` |
| JSON | `toJson()`, `toJsonElement()`, `Delta.fromJson(…)` |
| Attributes | `AttributeMaps.compose(a, b, keepNull, depth)`, `diff(a, b, depth)`, `invert(attr, base, depth)`, `transform(a, b, priority, depth)` |
| Iteration | `OpIterator(ops)`: `hasNext`, `next(length)`, `peek`, `peekLength`, `peekType`, `rest` |

The builders mutate the delta and return it, so calls chain. Every other operation returns a
new `Delta`. Two deltas are `==` when their ops are. The
[TypeScript README](../typescript/README.md) describes each method's semantics in detail;
they are the same here.

`AttributeMaps.compose`, `diff` and `transform` return `null` when the result would be empty.
`invert` returns an empty map instead.

### Embeds

Register an `EmbedHandler` so that `compose`, `invert` and `transform` can combine two values
of the same embed type:

```kotlin
Delta.registerEmbed("counter", object : EmbedHandler<Int> {
    override fun compose(a: Int, b: Int, keepNull: Boolean) = a + b
    override fun invert(a: Int, b: Int) = -a
    override fun transform(a: Int, b: Int, priority: Boolean) = b
})
```

The handler receives the value under the embed type's key, e.g. `3` for
`mapOf("counter" to 3)`. Handlers are registered process-wide.

### Errors

Malformed operations throw `IllegalArgumentException`:
- retaining an embed against text
- mismatched embed types
- an embed type with no registered handler
- `diff` on a delta that is not a document

Malformed JSON throws `kotlinx.serialization.SerializationException`.

## Differences from the TypeScript API

| TypeScript | Kotlin |
| --- | --- |
| `Op` is a loose object with optional `insert` / `retain` / `delete` | sealed `Op.Insert` / `Op.Retain` / `Op.Delete`, payloads `InsertText`, `InsertEmbed`, `RetainLength`, `RetainEmbed` |
| `namespace AttributeMap` | `object AttributeMaps` (the type itself is the `AttributeMap` typealias) |
| `Op.length(op)` | `op.length()` |
| `undefined` attributes / keys | `null` attributes; a key absent from the map |
| `Infinity` as the default `slice` end | `Int.MAX_VALUE` |
| `reduce(fn, initial)`, `eachLine(fn, newline)` | `reduce(initial, fn)`, `eachLine(newline, fn)`, so the lambda can trail |
| `partition` returns a tuple | returns a `Pair` |
| `diff(other, cursor)` | `diff(other)`: there is no cursor hint |
| `new Error(...)` | `IllegalArgumentException` |
| `JSON.stringify(delta.ops)` | `delta.toJson()`, or kotlinx.serialization |

The text diff behind `Delta.diff` is diff-match-patch, the library fast-diff is derived from,
run with semantic cleanup and no time limit. The edit scripts it produces may differ from
the TypeScript implementation's for the same input. The corpus therefore checks diffs by
their effect and their size, not by their exact ops.

## Text and UTF-16

Text is measured and indexed in **UTF-16 code units**, as in the reference implementation and
the wire format. A Kotlin `String` is already a sequence of UTF-16 code units, so
`Op.Insert(InsertText("😀")).length()` is 2, and slicing between the two halves of a surrogate
pair splits it, exactly as in TypeScript.

## Develop

From the repository root:

```sh
just test-kt     # ./gradlew test, including the declarative test corpus
just lint-kt     # ./gradlew ktlintCheck
just format-kt   # ./gradlew ktlintFormat
just ci-kt       # ./gradlew build: ktlint, tests and jars
just publish-local-kt  # ./gradlew publishToMavenLocal: install into ~/.m2/repository
```

Code style is [ktlint](https://pinterest.github.io/ktlint/)'s `ktlint_official`, configured in
[`.editorconfig`](./.editorconfig). The ktlint version is pinned in `build.gradle.kts`.

Or directly with `./gradlew build` in this directory. The Gradle wrapper pins Gradle;
running it requires a JDK 17+.

## License

BSD-3-Clause. See [LICENSE](./LICENSE) and [NOTICE.txt](./NOTICE.txt).
