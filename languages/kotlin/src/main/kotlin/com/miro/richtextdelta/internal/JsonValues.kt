package com.miro.richtextdelta.internal

import com.miro.richtextdelta.InsertEmbed
import com.miro.richtextdelta.InsertText
import com.miro.richtextdelta.Op
import com.miro.richtextdelta.RetainEmbed
import com.miro.richtextdelta.RetainLength
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.longOrNull

/**
 * Conversion between JSON and the plain Kotlin values attributes and embeds hold:
 * `Map<String, Any?>`, `List<Any?>`, `String`, `Boolean`, `null` and numbers
 * (`Int` where it fits, then `Long`, then `Double`).
 */
internal object JsonValues {
    fun decode(element: JsonElement): Any? =
        when (element) {
            JsonNull -> {
                null
            }

            is JsonObject -> {
                element.entries.associateTo(LinkedHashMap()) { (key, value) -> key to decode(value) }
            }

            is JsonArray -> {
                element.map(::decode)
            }

            is JsonPrimitive -> {
                when {
                    element.isString -> {
                        element.content
                    }

                    else -> {
                        element.booleanOrNull
                            ?: element.intOrNull
                            ?: element.longOrNull
                            ?: element.doubleOrNull
                            ?: throw SerializationException("unsupported JSON number: ${element.content}")
                    }
                }
            }
        }

    fun encode(value: Any?): JsonElement =
        when (value) {
            null -> {
                JsonNull
            }

            is JsonElement -> {
                value
            }

            is String -> {
                JsonPrimitive(value)
            }

            is Number -> {
                JsonPrimitive(value)
            }

            is Boolean -> {
                JsonPrimitive(value)
            }

            is Map<*, *> -> {
                JsonObject(
                    value.entries.associate { (key, nested) ->
                        val name = key as? String ?: throw SerializationException("JSON object keys must be strings, got $key")
                        name to encode(nested)
                    },
                )
            }

            is Iterable<*> -> {
                JsonArray(value.map(::encode))
            }

            is Array<*> -> {
                JsonArray(value.map(::encode))
            }

            else -> {
                throw SerializationException("cannot encode ${value::class.qualifiedName} as JSON")
            }
        }

    fun encodeOp(op: Op): JsonObject {
        val fields = LinkedHashMap<String, JsonElement>()
        when (op) {
            is Op.Delete -> {
                fields["delete"] = JsonPrimitive(op.length)
            }

            is Op.Retain -> {
                fields["retain"] =
                    when (val value = op.value) {
                        is RetainLength -> JsonPrimitive(value.length)
                        is RetainEmbed -> encode(value.embed)
                    }
            }

            is Op.Insert -> {
                fields["insert"] =
                    when (val value = op.value) {
                        is InsertText -> JsonPrimitive(value.text)
                        is InsertEmbed -> encode(value.embed)
                    }
            }
        }
        op.attributes?.let { fields["attributes"] = encode(it) }
        return JsonObject(fields)
    }

    fun decodeOp(element: JsonElement): Op {
        if (element !is JsonObject) throw SerializationException("an op must be a JSON object, got $element")
        val attributes =
            when (val raw = element["attributes"]) {
                null, JsonNull -> null
                is JsonObject -> asAttributeMap(decode(raw))
                else -> throw SerializationException("op attributes must be a JSON object, got $raw")
            }
        element["delete"]?.takeUnless { it is JsonNull }?.let { return Op.Delete(integer(it, "delete")) }
        element["retain"]?.takeUnless { it is JsonNull }?.let { retain ->
            return Op.Retain(
                if (isNumber(retain)) {
                    RetainLength(integer(retain, "retain"), attributes)
                } else {
                    RetainEmbed(decode(retain) as Any, attributes)
                },
            )
        }
        element["insert"]?.takeUnless { it is JsonNull }?.let { insert ->
            return Op.Insert(
                if (insert is JsonPrimitive && insert.isString) {
                    InsertText(insert.content, attributes)
                } else {
                    InsertEmbed(decode(insert) as Any, attributes)
                },
            )
        }
        throw SerializationException("an op must have one of insert, retain or delete, got $element")
    }

    private fun isNumber(element: JsonElement): Boolean =
        element is JsonPrimitive && element !is JsonNull && !element.isString && element.booleanOrNull == null

    private fun integer(
        element: JsonElement,
        field: String,
    ): Int =
        (element as? JsonPrimitive)?.takeUnless { it.isString }?.intOrNull
            ?: throw SerializationException("$field must be an integer, got $element")
}
