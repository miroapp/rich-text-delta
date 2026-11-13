package com.miro.richtextdelta

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class ReadmeExamplesTest {
    private fun delta(json: String) = Delta.fromJson(json)

    private val doc = Delta().insert("Hello ").insert("World", mapOf("bold" to true)).insert("\n")
    private val change = Delta().retain(6).retain(5, mapOf("italic" to true))

    @Test
    fun `build a document`() {
        assertEquals(
            """[{"insert":"Hello "},{"insert":"World","attributes":{"bold":true}},{"insert":"\n"}]""",
            doc.toJson(),
        )
    }

    @Test
    fun compose() {
        assertEquals(
            delta("""[{"insert":"Hello "},{"insert":"World","attributes":{"italic":true,"bold":true}},{"insert":"\n"}]"""),
            doc.compose(change),
        )
    }

    @Test
    fun invert() {
        val undo = change.invert(doc)
        assertEquals(delta("""[{"retain":6},{"retain":5,"attributes":{"italic":null}}]"""), undo)
        assertEquals(doc, doc.compose(change).compose(undo))
    }

    @Test
    fun transform() {
        val a = Delta().insert("A")
        val b = Delta().insert("B")
        assertEquals(delta("""[{"retain":1},{"insert":"B"}]"""), a.transform(b, true))
        assertEquals(delta("""[{"insert":"B"}]"""), a.transform(b, false))
    }

    @Test
    fun `transform index`() {
        val a = Delta().insert("A")
        assertEquals(0, a.transform(0, true))
        assertEquals(1, a.transform(0, false))
        assertEquals(1, a.transformPosition(0))
    }

    @Test
    fun diff() {
        assertEquals(delta("""[{"retain":5},{"insert":"!"}]"""), Delta().insert("Hello").diff(Delta().insert("Hello!")))
    }

    @Test
    fun `nested attributes merge key by key`() {
        val base = Delta().insert("x", mapOf("style" to mapOf("color" to "red", "size" to 12)))
        val change = Delta().retain(1, mapOf("style" to mapOf("color" to "blue")))
        assertEquals(
            delta("""[{"insert":"x","attributes":{"style":{"color":"blue","size":12}}}]"""),
            base.compose(change),
        )
    }

    @Test
    fun `pattern match ops`() {
        val ops =
            Delta()
                .insert("a")
                .insert(mapOf("image" to "cat.png"))
                .retain(2)
                .delete(3)
                .ops
        val described =
            ops.map { op ->
                when (op) {
                    is Op.Insert -> {
                        when (val value = op.value) {
                            is InsertText -> value.text
                            is InsertEmbed -> value.embed
                        }
                    }

                    is Op.Retain -> {
                        op.value
                    }

                    is Op.Delete -> {
                        op.length
                    }
                }
            }
        assertEquals(listOf("a", mapOf("image" to "cat.png"), RetainLength(2), 3), described)
    }
}
