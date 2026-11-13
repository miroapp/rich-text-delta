package com.miro.richtextdelta

import com.miro.richtextdelta.internal.JsonValues
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Assertions.fail
import org.junit.jupiter.api.DynamicContainer
import org.junit.jupiter.api.DynamicNode
import org.junit.jupiter.api.DynamicTest
import org.junit.jupiter.api.TestFactory
import org.snakeyaml.engine.v2.api.Load
import org.snakeyaml.engine.v2.api.LoadSettings
import java.math.BigDecimal
import java.nio.file.Path
import kotlin.io.path.Path
import kotlin.io.path.extension
import kotlin.io.path.invariantSeparatorsPathString
import kotlin.io.path.isRegularFile
import kotlin.io.path.readText
import kotlin.io.path.relativeTo
import kotlin.io.path.walk

private val CORPUS_ROOT: Path =
    Path(
        System.getProperty("corpus.root") ?: error("system property corpus.root is not set; run the tests through Gradle"),
    )

// --- corpus format -------------------------------------------------------

private enum class ParamType { DELTA, ATTRS, OP, BOOL, INT, CALLS }

private data class Param(
    val name: String,
    val type: ParamType,
)

/**
 * [params] lists every argument the method takes, receiver included. Positional order is
 * this port's calling convention; only the names are part of the corpus. A result of
 * `null` means the method returned nothing.
 */
private class MethodSpec(
    val params: List<Param>,
    val invoke: (List<Any?>) -> JsonElement?,
)

/** JSON-encoded values in the YAML, decoded before dispatch. */
private val JSON_TYPES = setOf(ParamType.DELTA, ParamType.ATTRS, ParamType.OP)

/** An instance method's receiver is an ordinary argument named `receiver`. */
private val RECEIVER = Param("receiver", ParamType.DELTA)

/**
 * Types with no meaningful absent value, so leaving one out — whether by omitting the key or
 * writing `null` — is an authoring error rather than a case. `bool` and `int` arguments all
 * have defaults, and an absent `attrs` argument is itself under test.
 */
private val REQUIRED_TYPES = setOf(ParamType.DELTA, ParamType.OP, ParamType.CALLS)

private fun delta(value: Any?) = value as Delta

@Suppress("UNCHECKED_CAST")
private fun attrs(value: Any?) = value as AttributeMap?

private fun attrsResult(value: AttributeMap?): JsonElement? = value?.let(AttributeMaps::toJsonElement)

private val METHODS: Map<String, MethodSpec> =
    mapOf(
        "Delta.compose" to
            MethodSpec(listOf(RECEIVER, Param("other", ParamType.DELTA))) { (receiver, other) ->
                delta(receiver).compose(delta(other)).toJsonElement()
            },
        "Delta.transform" to
            MethodSpec(
                listOf(RECEIVER, Param("other", ParamType.DELTA), Param("priority", ParamType.BOOL)),
            ) { (receiver, other, priority) ->
                delta(receiver).transform(delta(other), priority as Boolean? ?: false).toJsonElement()
            },
        "Delta.transformPosition" to
            MethodSpec(
                listOf(RECEIVER, Param("index", ParamType.INT), Param("priority", ParamType.BOOL)),
            ) { (receiver, index, priority) ->
                JsonPrimitive(delta(receiver).transformPosition(index as Int, priority as Boolean? ?: false))
            },
        "Delta.invert" to
            MethodSpec(listOf(RECEIVER, Param("base", ParamType.DELTA))) { (receiver, base) ->
                delta(receiver).invert(delta(base)).toJsonElement()
            },
        "Delta.diff" to
            MethodSpec(listOf(RECEIVER, Param("other", ParamType.DELTA))) { (receiver, other) ->
                delta(receiver).diff(delta(other)).toJsonElement()
            },
        "Delta.concat" to
            MethodSpec(listOf(RECEIVER, Param("other", ParamType.DELTA))) { (receiver, other) ->
                delta(receiver).concat(delta(other)).toJsonElement()
            },
        "Delta.chop" to
            MethodSpec(listOf(RECEIVER)) { (receiver) ->
                delta(receiver).chop().toJsonElement()
            },
        "Delta.slice" to
            MethodSpec(
                listOf(RECEIVER, Param("start", ParamType.INT), Param("end", ParamType.INT)),
            ) { (receiver, start, end) ->
                delta(receiver).slice(start as Int? ?: 0, end as Int? ?: Int.MAX_VALUE).toJsonElement()
            },
        "Delta.length" to
            MethodSpec(listOf(RECEIVER)) { (receiver) ->
                JsonPrimitive(delta(receiver).length())
            },
        "Delta.build" to
            MethodSpec(listOf(Param("calls", ParamType.CALLS))) { (calls) ->
                @Suppress("UNCHECKED_CAST")
                build(calls as List<Map<String, Any?>>).toJsonElement()
            },
        "AttributeMap.compose" to
            MethodSpec(
                listOf(
                    Param("a", ParamType.ATTRS),
                    Param("b", ParamType.ATTRS),
                    Param("keepNull", ParamType.BOOL),
                    Param("depth", ParamType.INT),
                ),
            ) { (a, b, keepNull, depth) ->
                attrsResult(
                    AttributeMaps.compose(
                        attrs(a),
                        attrs(b),
                        keepNull as Boolean? ?: false,
                        depth as Int? ?: AttributeMaps.MAX_RECURSION_DEPTH,
                    ),
                )
            },
        "AttributeMap.diff" to
            MethodSpec(
                listOf(Param("a", ParamType.ATTRS), Param("b", ParamType.ATTRS), Param("depth", ParamType.INT)),
            ) { (a, b, depth) ->
                attrsResult(AttributeMaps.diff(attrs(a), attrs(b), depth as Int? ?: AttributeMaps.MAX_RECURSION_DEPTH))
            },
        "AttributeMap.invert" to
            MethodSpec(
                listOf(Param("attr", ParamType.ATTRS), Param("base", ParamType.ATTRS), Param("depth", ParamType.INT)),
            ) { (attr, base, depth) ->
                attrsResult(
                    AttributeMaps.invert(attrs(attr), attrs(base), depth as Int? ?: AttributeMaps.MAX_RECURSION_DEPTH),
                )
            },
        "AttributeMap.transform" to
            MethodSpec(
                listOf(
                    Param("a", ParamType.ATTRS),
                    Param("b", ParamType.ATTRS),
                    Param("priority", ParamType.BOOL),
                    Param("depth", ParamType.INT),
                ),
            ) { (a, b, priority, depth) ->
                attrsResult(
                    AttributeMaps.transform(
                        attrs(a),
                        attrs(b),
                        priority as Boolean? ?: false,
                        depth as Int? ?: AttributeMaps.MAX_RECURSION_DEPTH,
                    ),
                )
            },
        "Op.length" to
            MethodSpec(listOf(Param("op", ParamType.OP))) { (op) ->
                JsonPrimitive((op as Op).length())
            },
    )

/**
 * An embed whose value is an ops array, composed/transformed/inverted by recursing into Delta
 * itself. Self-referential, so every port can implement it without any user-supplied logic.
 */
private object NestedDelta : EmbedHandler<Any?> {
    private fun delta(value: Any?) = Delta.fromJson(JsonValues.encode(value))

    private fun result(delta: Delta) = JsonValues.decode(delta.toJsonElement())

    override fun compose(
        a: Any?,
        b: Any?,
        keepNull: Boolean,
    ): Any? = result(delta(a).compose(delta(b)))

    override fun transform(
        a: Any?,
        b: Any?,
        priority: Boolean,
    ): Any? = result(delta(a).transform(delta(b), priority))

    override fun invert(
        a: Any?,
        b: Any?,
    ): Any? = result(delta(a).invert(delta(b)))
}

/** Named embed handlers a case may request via `embeds`. */
private val EMBED_HANDLERS: Map<String, EmbedHandler<Any?>> = mapOf("nested-delta" to NestedDelta)

/** Maps this implementation's error messages onto the corpus error kinds. */
private val ERROR_KINDS: List<Pair<Regex, String>> =
    listOf(
        Regex("^cannot retain a ") to "cannot-retain-non-embed",
        Regex("^embed types not matched: ") to "embed-types-mismatch",
        Regex("^no handlers for embed type ") to "no-embed-handler",
        Regex("^diff\\(\\) called (on|with) non-document$") to "diff-non-document",
    )

private val INVARIANTS = setOf("composes-to-other")

private class TestCase(
    private val raw: Map<String, Any?>,
) {
    val name: String? get() = raw["name"] as String?
    val method: String? get() = raw["method"] as String?

    @Suppress("UNCHECKED_CAST")
    val args: Map<String, Any?> get() = raw["args"] as Map<String, Any?>? ?: emptyMap()

    @Suppress("UNCHECKED_CAST")
    val embeds: Map<String, String> get() = raw["embeds"] as Map<String, String>? ?: emptyMap()

    val hasExpected: Boolean get() = raw.containsKey("expected")
    val expected: String? get() = raw["expected"] as String?

    @Suppress("UNCHECKED_CAST")
    val errorKind: String? get() = (raw["error"] as Map<String, Any?>?)?.get("kind") as String?
    val hasError: Boolean get() = raw["error"] != null
    val invariant: String? get() = raw["invariant"] as String?
    val maxInserted: Int get() = raw["maxInserted"] as Int
    val maxDeleted: Int get() = raw["maxDeleted"] as Int
}

// --- dispatch ------------------------------------------------------------

private fun build(calls: List<Map<String, Any?>>): Delta {
    val delta = Delta()
    for (call in calls) {
        @Suppress("UNCHECKED_CAST")
        val args = call["args"] as Map<String, Any?>? ?: emptyMap()
        val attributes = if (args.containsKey("attributes")) AttributeMaps.fromJson(args["attributes"] as String) else null
        when (call["op"]) {
            "insert" -> {
                when (val arg = JsonValues.decode(Json.parseToJsonElement(args["arg"] as String))) {
                    is String -> delta.insert(arg, attributes)
                    else -> delta.insert(arg as Any, attributes)
                }
            }

            "retain" -> {
                when (val arg = JsonValues.decode(Json.parseToJsonElement(args["arg"] as String))) {
                    is Number -> delta.retain(arg.toInt(), attributes)
                    else -> delta.retain(arg as Any, attributes)
                }
            }

            "delete" -> {
                delta.delete(args["length"] as Int)
            }

            "push" -> {
                delta.push(Op.fromJson(args["op"] as String))
            }

            else -> {
                error("unknown builder op: ${call["op"]}")
            }
        }
    }
    return delta
}

private fun decode(
    type: ParamType,
    raw: Any?,
): Any? {
    if (type !in JSON_TYPES) return raw
    val json = raw as String
    return when (type) {
        ParamType.DELTA -> Delta.fromJson(json)
        ParamType.ATTRS -> AttributeMaps.fromJson(json)
        ParamType.OP -> Op.fromJson(json)
        else -> error("unreachable")
    }
}

/**
 * Whether the case supplies an argument. A `null` counts as not supplied, and the method's
 * default is used: `attributes.yaml` spells out every argument and writes `null` for the
 * ones it does not supply, rather than omitting the key; both spellings mean the same thing
 * here. Unrelated to a `null` *inside* a JSON value, which is an attribute removal.
 */
private fun suppliedArg(
    testCase: TestCase,
    name: String,
): Boolean = testCase.args.containsKey(name) && testCase.args[name] != null

private fun positionalArgs(
    spec: MethodSpec,
    testCase: TestCase,
): List<Any?> =
    spec.params.map { param ->
        if (suppliedArg(testCase, param.name)) decode(param.type, testCase.args[param.name]) else null
    }

/**
 * Strict structural equality: objects are unordered key->value maps, arrays are ordered,
 * numbers compare by value, and an absent key is NOT equal to one holding an empty map.
 */
private fun structurallyEqual(
    a: JsonElement,
    b: JsonElement,
): Boolean =
    when {
        a is JsonObject && b is JsonObject -> {
            a.keys == b.keys && a.all { (key, value) -> structurallyEqual(value, b.getValue(key)) }
        }

        a is JsonArray && b is JsonArray -> {
            a.size == b.size && a.indices.all { structurallyEqual(a[it], b[it]) }
        }

        a is JsonNull || b is JsonNull -> {
            a == b
        }

        a is JsonPrimitive && b is JsonPrimitive -> {
            if (a.isString || b.isString) {
                a.isString == b.isString && a.content == b.content
            } else {
                val x = a.content.toBigDecimalOrNull()
                val y = b.content.toBigDecimalOrNull()
                if (x != null && y != null) x.compareTo(y) == 0 else a.content == b.content
            }
        }

        else -> {
            false
        }
    }

private fun String.toBigDecimalOrNull(): BigDecimal? =
    try {
        BigDecimal(this)
    } catch (_: NumberFormatException) {
        null
    }

private fun classify(error: Throwable): String {
    val message = error.message.orEmpty()
    return ERROR_KINDS.firstOrNull { (pattern) -> pattern.containsMatchIn(message) }?.second
        ?: fail("unclassified error, no corpus kind matches: $message", error)
}

private fun editSize(ops: List<Op>): Pair<Int, Int> {
    var inserted = 0
    var deleted = 0
    for (op in ops) {
        when (op) {
            is Op.Insert -> inserted += op.length()
            is Op.Delete -> deleted += op.length
            is Op.Retain -> Unit
        }
    }
    return inserted to deleted
}

// --- validation ----------------------------------------------------------

private fun validate(
    file: String,
    testCase: TestCase,
    seen: MutableSet<String>,
): MethodSpec {
    val name = testCase.name ?: error("$file: a case is missing `name`")
    val where = "$file :: $name"
    check(seen.add(name)) { "$where: duplicate case name within the file" }

    val method = testCase.method
    val spec = METHODS[method] ?: error("$where: unknown method `$method`")
    val allowed = spec.params.map { it.name }.toSet()
    for (key in testCase.args.keys) {
        check(key in allowed) { "$where: `$method` has no argument `$key`" }
    }
    for (param in spec.params) {
        check(param.type !in REQUIRED_TYPES || suppliedArg(testCase, param.name)) {
            "$where: `$method` requires argument `${param.name}`"
        }
    }

    val forms = listOf(testCase.hasExpected, testCase.hasError, testCase.invariant != null).count { it }
    check(forms == 1) { "$where: expected exactly one of `expected`, `error`, `invariant`" }
    if (testCase.hasError) {
        check(ERROR_KINDS.any { (_, kind) -> kind == testCase.errorKind }) {
            "$where: unknown error kind `${testCase.errorKind}`"
        }
    }
    testCase.invariant?.let { check(it in INVARIANTS) { "$where: unknown invariant `$it`" } }
    for (handler in testCase.embeds.values) {
        check(handler in EMBED_HANDLERS) { "$where: unknown embed handler `$handler`" }
    }
    return spec
}

// --- execution -----------------------------------------------------------

private fun run(
    file: String,
    testCase: TestCase,
    spec: MethodSpec,
) {
    val where = "$file :: ${testCase.name}"
    for ((type, handler) in testCase.embeds) {
        Delta.registerEmbed(type, EMBED_HANDLERS.getValue(handler))
    }
    try {
        val args = positionalArgs(spec, testCase)

        if (testCase.hasError) {
            val thrown = runCatching { spec.invoke(args) }.exceptionOrNull()
            assertNotNull(thrown, "$where: expected a thrown error")
            assertEquals(testCase.errorKind, classify(thrown!!), where)
            return
        }

        val actual = spec.invoke(args)

        if (testCase.invariant != null) {
            // `diff` decomposition is algorithm-dependent, so the corpus asserts that applying
            // the result reproduces the target document, plus a ceiling on edit size so a
            // degenerate delete-all-and-reinsert cannot pass.
            val result = Delta.fromJson(actual!!)
            val applied = Delta.fromJson(testCase.args["receiver"] as String).compose(result).toJsonElement()
            val other = Json.parseToJsonElement(testCase.args["other"] as String)
            assertTrue(structurallyEqual(applied, other)) {
                "$where: applying the diff must reproduce `other`\n  expected: $other\n  actual:   $applied\n  diff:     $actual"
            }
            val (inserted, deleted) = editSize(result.ops)
            assertTrue(inserted <= testCase.maxInserted) {
                "$where: inserted characters $inserted > ${testCase.maxInserted} (diff: $actual)"
            }
            assertTrue(deleted <= testCase.maxDeleted) {
                "$where: deleted characters $deleted > ${testCase.maxDeleted} (diff: $actual)"
            }
            return
        }

        val expected = testCase.expected
        if (expected == null) {
            assertNull(actual, "$where: expected no result")
            return
        }

        val expectedJson = Json.parseToJsonElement(expected)
        assertNotNull(actual, "$where: expected $expectedJson, got no result")
        assertTrue(structurallyEqual(actual!!, expectedJson)) {
            "$where\n  expected: $expectedJson\n  actual:   $actual"
        }
    } finally {
        for (type in testCase.embeds.keys + "delta") {
            Delta.unregisterEmbed(type)
        }
    }
}

// --- loading -------------------------------------------------------------

class DeclarativeTestCorpusTest {
    @TestFactory
    fun corpus(): List<DynamicNode> {
        val files =
            CORPUS_ROOT
                .walk()
                .filter { it.isRegularFile() && it.extension in setOf("yaml", "yml") }
                .sortedBy { it.invariantSeparatorsPathString }
                .toList()
        check(files.isNotEmpty()) { "no case files found under $CORPUS_ROOT" }
        val yaml = Load(LoadSettings.builder().build())

        return files.map { path ->
            val file = path.relativeTo(CORPUS_ROOT).invariantSeparatorsPathString

            @Suppress("UNCHECKED_CAST")
            val parsed = yaml.loadFromString(path.readText()) as Map<String, Any?>?

            @Suppress("UNCHECKED_CAST")
            val cases = (parsed?.get("tests") as List<Map<String, Any?>>?).orEmpty().map(::TestCase)
            val seen = mutableSetOf<String>()
            val tests =
                cases.map { testCase ->
                    val spec = validate(file, testCase, seen)
                    DynamicTest.dynamicTest(testCase.name) { run(file, testCase, spec) }
                }
            val nonEmpty =
                DynamicTest.dynamicTest("is non-empty") {
                    assertTrue(cases.isNotEmpty(), "$file: no cases")
                }
            DynamicContainer.dynamicContainer(file, path.toUri(), (listOf(nonEmpty) + tests).stream())
        }
    }
}
