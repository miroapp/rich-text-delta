package com.miro.richtextdelta

import com.miro.richtextdelta.internal.deepEqual
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import org.bitbucket.cowwoc.diffmatchpatch.DiffMatchPatch
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.min

private const val NULL_CHARACTER = "\u0000" // Placeholder char for embed in diff()

@Serializable(with = DeltaSerializer::class)
public class Delta(
    ops: List<Op> = emptyList(),
) {
    private val mutableOps: MutableList<Op> = ops.toMutableList()

    public val ops: List<Op> get() = mutableOps

    public fun insert(
        text: String,
        attributes: AttributeMap? = null,
    ): Delta {
        if (text.isEmpty()) return this
        return push(Op.Insert(InsertText(text, attributes?.ifEmpty { null })))
    }

    /** Inserts an embed. A [String] argument is inserted as text. */
    public fun insert(
        embed: Any,
        attributes: AttributeMap? = null,
    ): Delta {
        if (embed is String) return insert(embed, attributes)
        return push(Op.Insert(InsertEmbed(embed, attributes?.ifEmpty { null })))
    }

    public fun delete(length: Int): Delta {
        if (length <= 0) return this
        return push(Op.Delete(length))
    }

    public fun retain(
        length: Int,
        attributes: AttributeMap? = null,
    ): Delta {
        if (length <= 0) return this
        return push(Op.Retain(RetainLength(length, attributes?.ifEmpty { null })))
    }

    /** Retains an embed. A [Number] argument is retained as a length. */
    public fun retain(
        embed: Any,
        attributes: AttributeMap? = null,
    ): Delta {
        if (embed is Number) return retain(embed.toInt(), attributes)
        return push(Op.Retain(RetainEmbed(embed, attributes?.ifEmpty { null })))
    }

    public fun push(newOp: Op): Delta {
        val op = newOp.deepCopy()
        var index = mutableOps.size
        var lastOp = mutableOps.getOrNull(index - 1)
        if (lastOp != null) {
            if (op is Op.Delete && lastOp is Op.Delete) {
                mutableOps[index - 1] = Op.Delete(lastOp.length + op.length)
                return this
            }
            // Since it does not matter if we insert before or after deleting at the same index,
            // always prefer to insert first
            if (lastOp is Op.Delete && op is Op.Insert) {
                index -= 1
                lastOp = mutableOps.getOrNull(index - 1)
                if (lastOp == null) {
                    mutableOps.add(0, op)
                    return this
                }
            }
            if (deepEqual(op.attributes, lastOp.attributes)) {
                val text = (op as? Op.Insert)?.value as? InsertText
                val lastText = (lastOp as? Op.Insert)?.value as? InsertText
                if (text != null && lastText != null) {
                    mutableOps[index - 1] = Op.Insert(InsertText(lastText.text + text.text, op.attributes))
                    return this
                }
                val retain = (op as? Op.Retain)?.value as? RetainLength
                val lastRetain = (lastOp as? Op.Retain)?.value as? RetainLength
                if (retain != null && lastRetain != null) {
                    mutableOps[index - 1] = Op.Retain(RetainLength(lastRetain.length + retain.length, op.attributes))
                    return this
                }
            }
        }
        mutableOps.add(index, op)
        return this
    }

    public fun chop(): Delta {
        val lastOp = mutableOps.lastOrNull()
        if (lastOp is Op.Retain && lastOp.value is RetainLength && lastOp.attributes == null) {
            mutableOps.removeAt(mutableOps.size - 1)
        }
        return this
    }

    public fun filter(predicate: (op: Op, index: Int) -> Boolean): List<Op> = mutableOps.filterIndexed { index, op -> predicate(op, index) }

    public fun forEach(action: (op: Op, index: Int) -> Unit) {
        mutableOps.forEachIndexed { index, op -> action(op, index) }
    }

    public fun <T> map(transform: (op: Op, index: Int) -> T): List<T> = mutableOps.mapIndexed { index, op -> transform(op, index) }

    public fun partition(predicate: (op: Op) -> Boolean): Pair<List<Op>, List<Op>> = mutableOps.partition(predicate)

    public fun <T> reduce(
        initialValue: T,
        operation: (accumulator: T, op: Op, index: Int) -> T,
    ): T = mutableOps.foldIndexed(initialValue) { index, accumulator, op -> operation(accumulator, op, index) }

    public fun changeLength(): Int =
        reduce(0) { length, op, _ ->
            when (op) {
                is Op.Insert -> length + op.length()
                is Op.Delete -> length - op.length
                is Op.Retain -> length
            }
        }

    public fun length(): Int = reduce(0) { length, op, _ -> length + op.length() }

    public fun slice(
        start: Int = 0,
        end: Int = Int.MAX_VALUE,
    ): Delta {
        val ops = mutableListOf<Op>()
        val iter = OpIterator(mutableOps)
        var index = 0
        while (index < end && iter.hasNext()) {
            val nextOp: Op
            if (index < start) {
                nextOp = iter.next(start - index)
            } else {
                nextOp = iter.next(end - index)
                ops.add(nextOp)
            }
            index += nextOp.length()
        }
        return Delta(ops)
    }

    public fun compose(other: Delta): Delta {
        val thisIter = OpIterator(mutableOps)
        val otherIter = OpIterator(other.mutableOps)
        val ops = mutableListOf<Op>()
        val firstOther = otherIter.peek()
        val firstRetain = ((firstOther as? Op.Retain)?.value as? RetainLength)?.takeIf { it.attributes == null }
        if (firstRetain != null) {
            var firstLeft = firstRetain.length
            while (thisIter.peekType() == OpType.INSERT && thisIter.peekLength() <= firstLeft) {
                firstLeft -= thisIter.peekLength()
                ops.add(thisIter.next())
            }
            if (firstRetain.length - firstLeft > 0) {
                otherIter.next(firstRetain.length - firstLeft)
            }
        }
        val delta = Delta(ops)
        while (thisIter.hasNext() || otherIter.hasNext()) {
            if (otherIter.peekType() == OpType.INSERT) {
                delta.push(otherIter.next())
            } else if (thisIter.peekType() == OpType.DELETE) {
                delta.push(thisIter.next())
            } else {
                val length = min(thisIter.peekLength(), otherIter.peekLength())
                val thisOp = thisIter.next(length)
                val otherOp = otherIter.next(length)
                if (otherOp is Op.Retain && !otherOp.isEmptyRetain()) {
                    val thisRetainsLength = thisOp is Op.Retain && thisOp.value is RetainLength
                    // Preserve null when composing with a retain, otherwise remove it for inserts
                    val attributes = AttributeMaps.compose(thisOp.attributes, otherOp.attributes, thisRetainsLength)
                    val otherValue = otherOp.value
                    val newOp: Op =
                        if (thisRetainsLength) {
                            when (otherValue) {
                                is RetainLength -> Op.Retain(RetainLength(length, attributes))
                                is RetainEmbed -> Op.Retain(RetainEmbed(otherValue.embed, attributes))
                            }
                        } else if (otherValue is RetainLength) {
                            thisOp.withAttributes(attributes)
                        } else {
                            val retainsEmbed = thisOp is Op.Retain
                            val (embedType, thisData, otherData) =
                                getEmbedTypeAndData(payload(thisOp), (otherValue as RetainEmbed).embed)
                            val handler = getHandler(embedType)
                            val composed = mapOf(embedType to handler.compose(thisData, otherData, retainsEmbed))
                            if (retainsEmbed) {
                                Op.Retain(RetainEmbed(composed, attributes))
                            } else {
                                Op.Insert(InsertEmbed(composed, attributes))
                            }
                        }
                    delta.push(newOp)

                    // Optimization if rest of other is just retain
                    if (!otherIter.hasNext() && delta.mutableOps.last() == newOp) {
                        val rest = Delta(thisIter.rest())
                        return delta.concat(rest).chop()
                    }

                    // Other op should be delete, we could be an insert or retain
                    // Insert + delete cancels out
                } else if (otherOp is Op.Delete && thisOp is Op.Retain) {
                    delta.push(otherOp)
                }
            }
        }
        return delta.chop()
    }

    public fun concat(other: Delta): Delta {
        val delta = Delta(mutableOps)
        if (other.mutableOps.isNotEmpty()) {
            delta.push(other.mutableOps[0])
            delta.mutableOps.addAll(other.mutableOps.subList(1, other.mutableOps.size))
        }
        return delta
    }

    /**
     * The change that turns this document into [other]. Text is compared with diff-match-patch
     * (Myers' algorithm with semantic cleanup), with no time limit.
     */
    public fun diff(other: Delta): Delta {
        if (this === other) return Delta()
        val thisText = documentText(this, "with")
        val otherText = documentText(other, "on")
        val diffMatchPatch = DiffMatchPatch().apply { diffTimeout = 0f }
        val components = diffMatchPatch.diffMain(thisText, otherText, false)
        diffMatchPatch.diffCleanupSemantic(components)
        val retDelta = Delta()
        val thisIter = OpIterator(mutableOps)
        val otherIter = OpIterator(other.mutableOps)
        for (component in components) {
            var length = component.text.length
            while (length > 0) {
                val opLength: Int
                when (component.operation!!) {
                    DiffMatchPatch.Operation.INSERT -> {
                        opLength = min(otherIter.peekLength(), length)
                        retDelta.push(otherIter.next(opLength))
                    }

                    DiffMatchPatch.Operation.DELETE -> {
                        opLength = min(length, thisIter.peekLength())
                        thisIter.next(opLength)
                        retDelta.delete(opLength)
                    }

                    DiffMatchPatch.Operation.EQUAL -> {
                        opLength = min(min(thisIter.peekLength(), otherIter.peekLength()), length)
                        val thisOp = thisIter.next(opLength)
                        val otherOp = otherIter.next(opLength)
                        if (deepEqual(payload(thisOp), payload(otherOp))) {
                            retDelta.retain(opLength, AttributeMaps.diff(thisOp.attributes, otherOp.attributes))
                        } else {
                            retDelta.push(otherOp).delete(opLength)
                        }
                    }
                }
                length -= opLength
            }
        }
        return retDelta.chop()
    }

    /**
     * Calls [predicate] with each line of this document and the attributes of the newline that
     * ends it. Iteration stops early when [predicate] returns `false`.
     */
    public fun eachLine(
        newline: String = "\n",
        predicate: (line: Delta, attributes: AttributeMap, index: Int) -> Boolean,
    ) {
        val iter = OpIterator(mutableOps)
        var line = Delta()
        var i = 0
        while (iter.hasNext()) {
            if (iter.peekType() != OpType.INSERT) return
            val thisOp = iter.peek() as Op.Insert
            val start = thisOp.length() - iter.peekLength()
            val index = (thisOp.value as? InsertText)?.let { it.text.indexOf(newline, start) - start } ?: -1
            if (index < 0) {
                line.push(iter.next())
            } else if (index > 0) {
                line.push(iter.next(index))
            } else {
                if (!predicate(line, iter.next(1).attributes ?: emptyMap(), i)) return
                i += 1
                line = Delta()
            }
        }
        if (line.length() > 0) {
            predicate(line, emptyMap(), i)
        }
    }

    public fun invert(base: Delta): Delta {
        val inverted = Delta()
        reduce(0) { baseIndex, op, _ ->
            val retainValue = (op as? Op.Retain)?.value
            when {
                op is Op.Insert -> {
                    inverted.delete(op.length())
                    baseIndex
                }

                retainValue is RetainLength && op.attributes == null -> {
                    inverted.retain(retainValue.length)
                    baseIndex + retainValue.length
                }

                op is Op.Delete || retainValue is RetainLength -> {
                    val length = op.length()
                    val slice = base.slice(baseIndex, baseIndex + length)
                    slice.forEach { baseOp, _ ->
                        if (op is Op.Delete) {
                            inverted.push(baseOp)
                        } else if (op.attributes != null) {
                            inverted.retain(baseOp.length(), AttributeMaps.invert(op.attributes, baseOp.attributes))
                        }
                    }
                    baseIndex + length
                }

                retainValue is RetainEmbed -> {
                    val slice = base.slice(baseIndex, baseIndex + 1)
                    val baseOp = OpIterator(slice.mutableOps).next()
                    val (embedType, opData, baseOpData) =
                        getEmbedTypeAndData(retainValue.embed, (baseOp as? Op.Insert)?.let(::payload))
                    val handler = getHandler(embedType)
                    inverted.retain(
                        mapOf(embedType to handler.invert(opData, baseOpData)),
                        AttributeMaps.invert(op.attributes, baseOp.attributes),
                    )
                    baseIndex + 1
                }

                else -> {
                    baseIndex
                }
            }
        }
        return inverted.chop()
    }

    public fun transform(
        index: Int,
        priority: Boolean = false,
    ): Int = transformPosition(index, priority)

    public fun transform(
        other: Delta,
        priority: Boolean = false,
    ): Delta {
        val thisIter = OpIterator(mutableOps)
        val otherIter = OpIterator(other.mutableOps)
        val delta = Delta()
        while (thisIter.hasNext() || otherIter.hasNext()) {
            if (thisIter.peekType() == OpType.INSERT && (priority || otherIter.peekType() != OpType.INSERT)) {
                delta.retain(thisIter.next().length())
            } else if (otherIter.peekType() == OpType.INSERT) {
                delta.push(otherIter.next())
            } else {
                val length = min(thisIter.peekLength(), otherIter.peekLength())
                val thisOp = thisIter.next(length)
                val otherOp = otherIter.next(length)
                if (thisOp is Op.Delete && thisOp.length != 0) {
                    // Our delete either makes their delete redundant or removes their retain
                    continue
                } else if (otherOp is Op.Delete && otherOp.length != 0) {
                    delta.push(otherOp)
                } else {
                    val thisData = ((thisOp as? Op.Retain)?.value as? RetainEmbed)?.embed
                    val otherData = ((otherOp as? Op.Retain)?.value as? RetainEmbed)?.embed
                    var transformedData: Any? = otherData
                    if (thisData is Map<*, *> && otherData is Map<*, *>) {
                        val embedType = thisData.keys.firstOrNull() as? String
                        if (embedType != null && embedType == otherData.keys.firstOrNull()) {
                            val handler = getHandler(embedType)
                            transformedData =
                                mapOf(
                                    embedType to handler.transform(thisData[embedType], otherData[embedType], priority),
                                )
                        }
                    }

                    // We retain either their retain or insert
                    val attributes = AttributeMaps.transform(thisOp.attributes, otherOp.attributes, priority)
                    if (transformedData != null) {
                        delta.retain(transformedData, attributes)
                    } else {
                        delta.retain(length, attributes)
                    }
                }
            }
        }
        return delta.chop()
    }

    public fun transformPosition(
        index: Int,
        priority: Boolean = false,
    ): Int {
        var index = index
        val thisIter = OpIterator(mutableOps)
        var offset = 0
        while (thisIter.hasNext() && offset <= index) {
            val length = thisIter.peekLength()
            val nextType = thisIter.peekType()
            thisIter.next()
            if (nextType == OpType.DELETE) {
                index -= min(length, index - offset)
                continue
            } else if (nextType == OpType.INSERT && (offset < index || !priority)) {
                index += length
            }
            offset += length
        }
        return index
    }

    public fun toJsonElement(): JsonArray = JsonArray(mutableOps.map(Op::toJsonElement))

    public fun toJson(): String = toJsonElement().toString()

    override fun equals(other: Any?): Boolean = other is Delta && mutableOps == other.mutableOps

    override fun hashCode(): Int = mutableOps.hashCode()

    override fun toString(): String = "Delta(${toJson()})"

    public companion object {
        private val handlers = ConcurrentHashMap<String, EmbedHandler<Any?>>()

        @Suppress("UNCHECKED_CAST")
        public fun <T> registerEmbed(
            embedType: String,
            handler: EmbedHandler<T>,
        ) {
            handlers[embedType] = handler as EmbedHandler<Any?>
        }

        public fun unregisterEmbed(embedType: String) {
            handlers.remove(embedType)
        }

        private fun getHandler(embedType: String): EmbedHandler<Any?> =
            handlers[embedType] ?: throw IllegalArgumentException("no handlers for embed type \"$embedType\"")

        /** Decodes a JSON array of ops, or an object holding one under `ops`. */
        public fun fromJson(element: JsonElement): Delta {
            val ops =
                when (element) {
                    is JsonArray -> element
                    is JsonObject -> element["ops"] as? JsonArray
                    else -> null
                } ?: throw SerializationException("a delta must be a JSON array of ops, got $element")
            return Delta(ops.map(Op::fromJson))
        }

        public fun fromJson(json: String): Delta = fromJson(Json.parseToJsonElement(json))
    }
}

/** A retain of length 0, which carries no change. */
private fun Op.Retain.isEmptyRetain(): Boolean = (value as? RetainLength)?.length == 0

/** The text, embed or length an op carries, or `null` for a delete. */
private fun payload(op: Op): Any? =
    when (op) {
        is Op.Delete -> {
            null
        }

        is Op.Insert -> {
            when (val value = op.value) {
                is InsertText -> value.text
                is InsertEmbed -> value.embed
            }
        }

        is Op.Retain -> {
            when (val value = op.value) {
                is RetainLength -> value.length
                is RetainEmbed -> value.embed
            }
        }
    }

private fun getEmbedTypeAndData(
    a: Any?,
    b: Any?,
): Triple<String, Any?, Any?> {
    if (a !is Map<*, *>) throw IllegalArgumentException("cannot retain a ${describe(a)}")
    if (b !is Map<*, *>) throw IllegalArgumentException("cannot retain a ${describe(b)}")
    val embedType = a.keys.firstOrNull() as? String
    val otherType = b.keys.firstOrNull() as? String
    if (embedType.isNullOrEmpty() || embedType != otherType) {
        throw IllegalArgumentException("embed types not matched: $embedType != $otherType")
    }
    return Triple(embedType, a[embedType], b[embedType])
}

private fun describe(value: Any?): String =
    when (value) {
        null -> "null"
        is String -> "string"
        is Number -> "number"
        is Boolean -> "boolean"
        is List<*> -> "list"
        else -> value::class.simpleName ?: "value"
    }

private fun documentText(
    delta: Delta,
    prep: String,
): String =
    delta.ops.joinToString("") { op ->
        val value = (op as? Op.Insert)?.value ?: throw IllegalArgumentException("diff() called $prep non-document")
        when (value) {
            is InsertText -> value.text
            is InsertEmbed -> NULL_CHARACTER
        }
    }
