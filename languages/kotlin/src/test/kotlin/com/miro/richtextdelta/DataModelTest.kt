package com.miro.richtextdelta

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNotEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertSame
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class DataModelTest {
    @Test
    fun `builders mutate and return the same delta`() {
        val delta = Delta()
        assertSame(delta, delta.insert("a"))
        assertSame(delta, delta.retain(1))
        assertSame(delta, delta.delete(1))
        assertEquals(3, delta.ops.size)
    }

    @Test
    fun `builders treat null and empty attributes as none`() {
        assertNull(
            Delta()
                .insert("a", emptyMap())
                .ops
                .single()
                .attributes,
        )
        assertNull(
            Delta()
                .retain(1, emptyMap())
                .ops
                .single()
                .attributes,
        )
        assertEquals(Delta().insert("a"), Delta().insert("a", null))
    }

    @Test
    fun `ops keep explicitly empty attributes`() {
        assertEquals(emptyMap<String, Any?>(), Op.Insert(InsertText("a", emptyMap())).attributes)
    }

    @Test
    fun `insert of a String embed is text`() {
        val text: Any = "abc"
        assertEquals(Delta().insert("abc"), Delta().insert(text))
    }

    @Test
    fun `retain of a Number embed is a length`() {
        val length: Any = 3L
        assertEquals(Delta().retain(3), Delta().retain(length))
    }

    @Test
    fun `embeds reject text and lengths`() {
        assertThrows<IllegalArgumentException> { InsertEmbed("abc") }
        assertThrows<IllegalArgumentException> { RetainEmbed(3) }
    }

    @Test
    fun `equality is by ops`() {
        assertEquals(Delta().insert("ab"), Delta().insert("a").insert("b"))
        assertEquals(Delta().insert("ab").hashCode(), Delta().insert("a").insert("b").hashCode())
        assertNotEquals(Delta().insert("a"), Delta().insert("a", mapOf("bold" to true)))
    }

    @Test
    fun `numbers compare by value in attributes`() {
        assertNull(AttributeMaps.diff(mapOf("size" to 1), mapOf("size" to 1L)))
        assertNull(AttributeMaps.diff(mapOf("size" to 1), mapOf("size" to 1.0)))
    }

    @Test
    fun `null attribute value is a removal`() {
        val doc = Delta().insert("a", mapOf("bold" to true, "italic" to true))
        assertEquals(
            Delta().insert("a", mapOf("italic" to true)),
            doc.compose(Delta().retain(1, mapOf("bold" to null))),
        )
    }

    @Test
    fun `length is in UTF-16 code units`() {
        assertEquals(2, Op.Insert(InsertText("😀")).length())
        assertEquals(1, Op.Insert(InsertEmbed(mapOf("image" to "cat.png"))).length())
        val sliced = Delta().insert("😀").slice(0, 1)
        assertEquals(Delta().insert("\uD83D"), sliced)
    }

    @Test
    fun `utility methods`() {
        val delta = Delta().insert("ab").retain(2).delete(3)
        assertEquals(listOf(Op.Delete(3)), delta.filter { op, _ -> op is Op.Delete })
        assertEquals(listOf(2, 2, 3), delta.map { op, _ -> op.length() })
        assertEquals(7, delta.reduce(0) { acc, op, _ -> acc + op.length() })
        val (inserts, others) = delta.partition { it is Op.Insert }
        assertEquals(1, inserts.size)
        assertEquals(2, others.size)
        val indexes = mutableListOf<Int>()
        delta.forEach { _, index -> indexes += index }
        assertEquals(listOf(0, 1, 2), indexes)
        assertEquals(7, delta.length())
        assertEquals(-1, delta.changeLength())
    }

    @Test
    fun `slice defaults to the end`() {
        assertEquals(Delta().insert("llo"), Delta().insert("Hello").slice(2))
    }

    @Test
    fun `chop removes a trailing plain retain`() {
        assertEquals(Delta().insert("a"), Delta().insert("a").retain(3).chop())
        val formatted = Delta().insert("a").retain(3, mapOf("bold" to true))
        assertEquals(formatted, Delta(formatted.ops).chop())
    }

    @Test
    fun `concat merges adjacent ops`() {
        assertEquals(Delta().insert("ab"), Delta().insert("a").concat(Delta().insert("b")))
    }

    @Test
    fun `eachLine passes line, newline attributes and index`() {
        val doc =
            Delta()
                .insert("Title")
                .insert("\n", mapOf("header" to 1))
                .insert("Body\nTail")
        val lines = mutableListOf<Triple<Delta, AttributeMap, Int>>()
        doc.eachLine { line, attributes, index ->
            lines += Triple(line, attributes, index)
            true
        }
        assertEquals(
            listOf(
                Triple(Delta().insert("Title"), mapOf("header" to 1), 0),
                Triple(Delta().insert("Body"), emptyMap(), 1),
                Triple(Delta().insert("Tail"), emptyMap(), 2),
            ),
            lines,
        )
    }

    @Test
    fun `eachLine stops when the lambda returns false`() {
        var calls = 0
        Delta().insert("a\nb\nc\n").eachLine { _, _, _ ->
            calls++
            false
        }
        assertEquals(1, calls)
    }

    @Test
    fun `eachLine with a custom newline`() {
        val lines = mutableListOf<Delta>()
        Delta().insert("a|b").eachLine("|") { line, _, _ -> lines.add(line) }
        assertEquals(listOf(Delta().insert("a"), Delta().insert("b")), lines)
    }

    @Test
    fun `AttributeMaps return null or empty when nothing is left`() {
        assertNull(AttributeMaps.compose(mapOf("bold" to true), mapOf("bold" to null)))
        assertEquals(mapOf("bold" to null), AttributeMaps.compose(null, mapOf("bold" to null), keepNull = true))
        assertNull(AttributeMaps.diff(mapOf("bold" to true), mapOf("bold" to true)))
        assertNull(AttributeMaps.transform(mapOf("bold" to true), mapOf("bold" to false), priority = true))
        assertEquals(mapOf("bold" to false), AttributeMaps.transform(mapOf("bold" to true), mapOf("bold" to false)))
        assertEquals(emptyMap<String, Any?>(), AttributeMaps.invert(mapOf("bold" to true), mapOf("bold" to true)))
    }

    @Test
    fun `AttributeMaps depth limits recursion`() {
        val a = mapOf("style" to mapOf("color" to "red", "size" to 12))
        val b = mapOf("style" to mapOf("color" to "blue"))
        assertEquals(mapOf("style" to mapOf("color" to "blue", "size" to 12)), AttributeMaps.compose(a, b))
        assertEquals(b, AttributeMaps.compose(a, b, depth = 1))
    }

    @Test
    fun `OpIterator`() {
        val iter =
            OpIterator(
                Delta()
                    .insert("Hello")
                    .retain(3)
                    .delete(2)
                    .ops,
            )
        assertTrue(iter.hasNext())
        assertEquals(OpType.INSERT, iter.peekType())
        assertEquals(5, iter.peekLength())
        assertEquals(Op.Insert(InsertText("He")), iter.next(2))
        assertEquals(3, iter.peekLength())
        assertEquals(Op.Insert(InsertText("Hello")), iter.peek())
        assertEquals(Op.Insert(InsertText("llo")), iter.next())
        assertEquals(OpType.RETAIN, iter.peekType())
        assertEquals(listOf(Op.Retain(RetainLength(3)), Op.Delete(2)), iter.rest())
        iter.next()
        assertEquals(OpType.DELETE, iter.peekType())
        iter.next()
        assertFalse(iter.hasNext())
        assertEquals(Op.Retain(RetainLength(Int.MAX_VALUE)), iter.next())
    }

    @Test
    fun `malformed operations throw IllegalArgumentException`() {
        assertThrows<IllegalArgumentException> {
            Delta().insert("a").compose(Delta().retain(mapOf("image" to "cat.png")))
        }
        assertThrows<IllegalArgumentException> {
            Delta().insert(mapOf("image" to "a")).compose(Delta().retain(mapOf("video" to "b")))
        }
        assertThrows<IllegalArgumentException> {
            Delta().insert(mapOf("unregistered" to 1)).compose(Delta().retain(mapOf("unregistered" to 2)))
        }
        assertThrows<IllegalArgumentException> { Delta().retain(1).diff(Delta().insert("a")) }
        assertThrows<IllegalArgumentException> { Delta().insert("a").diff(Delta().delete(1)) }
    }
}
