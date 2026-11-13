package com.miro.richtextdelta.internal

import kotlinx.serialization.json.JsonElement
import java.math.BigDecimal
import java.math.BigInteger

internal fun isNestedMap(value: Any?): Boolean = value is Map<*, *>

@Suppress("UNCHECKED_CAST")
internal fun asAttributeMap(value: Any?): Map<String, Any?> = value as Map<String, Any?>

/**
 * Deep value equality: maps are unordered, lists are ordered, numbers compare by value
 * whatever their boxed type, and booleans never equal numbers.
 */
internal fun deepEqual(
    a: Any?,
    b: Any?,
): Boolean {
    if (a === b) return true
    if (a == null || b == null) return false
    return when {
        a is Boolean || b is Boolean -> {
            a == b
        }

        a is Number && b is Number -> {
            numbersEqual(a, b)
        }

        a is Map<*, *> && b is Map<*, *> -> {
            a.size == b.size && a.all { (key, value) -> b.containsKey(key) && deepEqual(value, b[key]) }
        }

        a is List<*> && b is List<*> -> {
            a.size == b.size && a.indices.all { deepEqual(a[it], b[it]) }
        }

        else -> {
            a == b
        }
    }
}

/** Whether [key] is absent from both maps, or present in both with equal values. */
internal fun sameEntry(
    a: Map<String, Any?>,
    b: Map<String, Any?>,
    key: String,
): Boolean = a.containsKey(key) == b.containsKey(key) && deepEqual(a[key], b[key])

internal fun deepCopy(value: Any?): Any? =
    when (value) {
        is JsonElement -> value
        is Map<*, *> -> value.entries.associateTo(LinkedHashMap()) { (key, nested) -> key to deepCopy(nested) }
        is List<*> -> value.map(::deepCopy)
        else -> value
    }

internal fun copyAttributes(attributes: Map<String, Any?>?): Map<String, Any?>? = attributes?.let { asAttributeMap(deepCopy(it)) }

private fun numbersEqual(
    a: Number,
    b: Number,
): Boolean {
    val x = a.toBigDecimalOrNull()
    val y = b.toBigDecimalOrNull()
    if (x != null && y != null) return x.compareTo(y) == 0
    val dx = a.toDouble()
    val dy = b.toDouble()
    return dx == dy || (dx.isNaN() && dy.isNaN())
}

private fun Number.toBigDecimalOrNull(): BigDecimal? =
    when (this) {
        is BigDecimal -> this
        is BigInteger -> BigDecimal(this)
        is Double, is Float -> toDouble().takeIf { it.isFinite() }?.let(BigDecimal::valueOf)
        else -> BigDecimal.valueOf(toLong())
    }
