package com.miro.richtextdelta

import com.miro.richtextdelta.internal.JsonValues
import com.miro.richtextdelta.internal.copyAttributes
import com.miro.richtextdelta.internal.deepCopy
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

/** Length of an op that never ends, such as the one past the end of an [OpIterator]. */
internal const val UNBOUNDED: Int = Int.MAX_VALUE

@Serializable(with = OpSerializer::class)
public sealed interface Op {
    public val attributes: AttributeMap?

    public data class Insert(
        val value: InsertValue,
    ) : Op {
        override val attributes: AttributeMap? get() = value.attributes
    }

    public data class Retain(
        val value: RetainValue,
    ) : Op {
        override val attributes: AttributeMap? get() = value.attributes
    }

    public data class Delete(
        val length: Int,
    ) : Op {
        override val attributes: AttributeMap? get() = null
    }

    /** The length this op contributes to a document. Text is measured in UTF-16 code units, embeds count as 1. */
    public fun length(): Int =
        when (this) {
            is Delete -> {
                length
            }

            is Retain -> {
                when (value) {
                    is RetainLength -> value.length
                    is RetainEmbed -> 1
                }
            }

            is Insert -> {
                when (value) {
                    is InsertText -> value.text.length
                    is InsertEmbed -> 1
                }
            }
        }

    public fun toJsonElement(): JsonObject = JsonValues.encodeOp(this)

    public fun toJson(): String = toJsonElement().toString()

    public companion object {
        public fun fromJson(element: JsonElement): Op = JsonValues.decodeOp(element)

        public fun fromJson(json: String): Op = fromJson(Json.parseToJsonElement(json))
    }
}

public sealed interface InsertValue {
    public val attributes: AttributeMap?
}

public data class InsertText(
    val text: String,
    override val attributes: AttributeMap? = null,
) : InsertValue

/** An embed is any non-text value; by convention a map holding a single key, the embed type. */
public data class InsertEmbed(
    val embed: Any,
    override val attributes: AttributeMap? = null,
) : InsertValue {
    init {
        require(embed !is String) { "an embed cannot be a String, use InsertText" }
    }
}

public sealed interface RetainValue {
    public val attributes: AttributeMap?
}

public data class RetainLength(
    val length: Int,
    override val attributes: AttributeMap? = null,
) : RetainValue

public data class RetainEmbed(
    val embed: Any,
    override val attributes: AttributeMap? = null,
) : RetainValue {
    init {
        require(embed !is Number) { "an embed cannot be a Number, use RetainLength" }
    }
}

internal fun Op.deepCopy(): Op =
    when (this) {
        is Op.Delete -> {
            this
        }

        is Op.Insert -> {
            Op.Insert(
                when (value) {
                    is InsertText -> value.copy(attributes = copyAttributes(value.attributes))
                    is InsertEmbed -> InsertEmbed(deepCopy(value.embed) as Any, copyAttributes(value.attributes))
                },
            )
        }

        is Op.Retain -> {
            Op.Retain(
                when (value) {
                    is RetainLength -> value.copy(attributes = copyAttributes(value.attributes))
                    is RetainEmbed -> RetainEmbed(deepCopy(value.embed) as Any, copyAttributes(value.attributes))
                },
            )
        }
    }

internal fun Op.withAttributes(attributes: AttributeMap?): Op =
    when (this) {
        is Op.Delete -> {
            this
        }

        is Op.Insert -> {
            Op.Insert(
                when (value) {
                    is InsertText -> value.copy(attributes = attributes)
                    is InsertEmbed -> value.copy(attributes = attributes)
                },
            )
        }

        is Op.Retain -> {
            Op.Retain(
                when (value) {
                    is RetainLength -> value.copy(attributes = attributes)
                    is RetainEmbed -> value.copy(attributes = attributes)
                },
            )
        }
    }
