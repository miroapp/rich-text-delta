package com.miro.richtextdelta

public enum class OpType { INSERT, RETAIN, DELETE }

public class OpIterator(
    public val ops: List<Op>,
) {
    public var index: Int = 0
        private set
    public var offset: Int = 0
        private set

    public fun hasNext(): Boolean = peekLength() < UNBOUNDED

    /** The next [length] units, or the rest of the current op when [length] is omitted or 0. */
    public fun next(length: Int = UNBOUNDED): Op {
        var length = if (length == 0) UNBOUNDED else length
        val nextOp = ops.getOrNull(index) ?: return Op.Retain(RetainLength(UNBOUNDED))
        val offset = this.offset
        val opLength = nextOp.length()
        if (length >= opLength - offset) {
            length = opLength - offset
            this.index += 1
            this.offset = 0
        } else {
            this.offset += length
        }
        return when (nextOp) {
            is Op.Delete -> {
                Op.Delete(length)
            }

            is Op.Retain -> {
                when (val value = nextOp.value) {
                    is RetainLength -> Op.Retain(RetainLength(length, value.attributes))

                    // offset should == 0, length should == 1
                    is RetainEmbed -> nextOp
                }
            }

            is Op.Insert -> {
                when (val value = nextOp.value) {
                    is InsertText -> Op.Insert(InsertText(value.text.substring(offset, offset + length), value.attributes))

                    // offset should == 0, length should == 1
                    is InsertEmbed -> nextOp
                }
            }
        }
    }

    public fun peek(): Op? = ops.getOrNull(index)

    public fun peekLength(): Int {
        // Should never return 0 if our index is being managed correctly
        val op = ops.getOrNull(index) ?: return UNBOUNDED
        return op.length() - offset
    }

    public fun peekType(): OpType =
        when (ops.getOrNull(index)) {
            is Op.Delete -> OpType.DELETE
            is Op.Insert -> OpType.INSERT
            is Op.Retain, null -> OpType.RETAIN
        }

    public fun rest(): List<Op> {
        if (!hasNext()) return emptyList()
        if (offset == 0) return ops.subList(index, ops.size).toList()
        val offset = this.offset
        val index = this.index
        val next = next()
        val rest = ops.subList(this.index, ops.size)
        this.offset = offset
        this.index = index
        return listOf(next) + rest
    }
}
