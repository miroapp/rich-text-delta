package com.miro.richtextdelta

import com.miro.richtextdelta.internal.JsonValues
import com.miro.richtextdelta.internal.asAttributeMap
import com.miro.richtextdelta.internal.deepCopy
import com.miro.richtextdelta.internal.isNestedMap
import com.miro.richtextdelta.internal.sameEntry
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject

/**
 * Formatting attributes. A key mapped to `null` is a removal; a key that is absent is
 * simply not set. Values may themselves be attribute maps, which every operation
 * recurses into.
 */
public typealias AttributeMap = Map<String, Any?>

public object AttributeMaps {
    public const val MAX_RECURSION_DEPTH: Int = 100

    public fun compose(
        a: AttributeMap? = null,
        b: AttributeMap? = null,
        keepNull: Boolean = false,
        depth: Int = MAX_RECURSION_DEPTH,
    ): AttributeMap? {
        val left = a.orEmpty()
        val right = b.orEmpty()
        val attributes = LinkedHashMap<String, Any?>()
        for ((key, value) in right) {
            if (keepNull || value != null) {
                attributes[key] = value
            }
        }
        for ((key, value) in left) {
            val other = right[key]
            if (isNestedMap(value) && isNestedMap(other) && depth > 1) {
                val nested = compose(asAttributeMap(value), asAttributeMap(other), keepNull, depth - 1)
                if (nested == null) {
                    attributes.remove(key)
                } else {
                    attributes[key] = nested
                }
            } else if (!right.containsKey(key)) {
                attributes[key] = deepCopy(value)
            }
        }
        return attributes.ifEmpty { null }
    }

    public fun diff(
        a: AttributeMap? = null,
        b: AttributeMap? = null,
        depth: Int = MAX_RECURSION_DEPTH,
    ): AttributeMap? {
        val left = a.orEmpty()
        val right = b.orEmpty()
        val keys = LinkedHashSet(left.keys).apply { addAll(right.keys) }
        val attributes = LinkedHashMap<String, Any?>()
        for (key in keys) {
            if (sameEntry(left, right, key)) continue
            val value = left[key]
            val other = right[key]
            if (isNestedMap(value) && isNestedMap(other) && depth > 1) {
                diff(asAttributeMap(value), asAttributeMap(other), depth - 1)?.let { attributes[key] = it }
            } else {
                attributes[key] = other
            }
        }
        return attributes.ifEmpty { null }
    }

    public fun invert(
        attr: AttributeMap? = null,
        base: AttributeMap? = null,
        depth: Int = MAX_RECURSION_DEPTH,
    ): AttributeMap {
        val change = attr.orEmpty()
        val original = base.orEmpty()
        val inverted = LinkedHashMap<String, Any?>()
        for ((key, baseValue) in original) {
            if (sameEntry(original, change, key) || !change.containsKey(key)) continue
            val value = change[key]
            if (isNestedMap(baseValue) && isNestedMap(value) && depth > 1) {
                val nested = invert(asAttributeMap(value), asAttributeMap(baseValue), depth - 1)
                if (nested.isNotEmpty()) {
                    inverted[key] = nested
                }
            } else {
                inverted[key] = baseValue
            }
        }
        for (key in change.keys) {
            if (!sameEntry(change, original, key) && !original.containsKey(key)) {
                inverted[key] = null
            }
        }
        return inverted
    }

    public fun transform(
        a: AttributeMap?,
        b: AttributeMap?,
        priority: Boolean = false,
        depth: Int = MAX_RECURSION_DEPTH,
    ): AttributeMap? {
        if (a == null) return b
        if (b == null) return null
        // b is unchanged when a doesn't have priority
        if (!priority) return b
        val attributes = LinkedHashMap<String, Any?>()
        for ((key, value) in b) {
            val other = a[key]
            if (isNestedMap(other) && isNestedMap(value) && depth > 1) {
                transform(asAttributeMap(other), asAttributeMap(value), priority, depth - 1)
                    ?.let { attributes[key] = it }
            } else if (!a.containsKey(key)) {
                attributes[key] = value
            }
        }
        return attributes.ifEmpty { null }
    }

    /** [attributes] as a JSON object, or [JsonNull] when there are none. */
    public fun toJsonElement(attributes: AttributeMap?): JsonElement = attributes?.let(JsonValues::encode) ?: JsonNull

    public fun toJson(attributes: AttributeMap?): String = toJsonElement(attributes).toString()

    /** Decodes a JSON object, or `null` for a JSON `null`. */
    public fun fromJson(element: JsonElement): AttributeMap? =
        when (element) {
            JsonNull -> null
            is JsonObject -> asAttributeMap(JsonValues.decode(element))
            else -> throw SerializationException("attributes must be a JSON object, got $element")
        }

    public fun fromJson(json: String): AttributeMap? = fromJson(Json.parseToJsonElement(json))
}
