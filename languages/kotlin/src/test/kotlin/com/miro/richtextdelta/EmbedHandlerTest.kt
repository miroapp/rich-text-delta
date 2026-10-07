package com.miro.richtextdelta

import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class EmbedHandlerTest {
    private val embedType = "embedHandlerTestCounter"

    private fun counter(n: Int) = mapOf(embedType to n)

    @BeforeEach
    fun register() {
        Delta.registerEmbed(
            embedType,
            object : EmbedHandler<Int> {
                override fun compose(
                    a: Int,
                    b: Int,
                    keepNull: Boolean,
                ) = a + b

                override fun invert(
                    a: Int,
                    b: Int,
                ) = -a

                override fun transform(
                    a: Int,
                    b: Int,
                    priority: Boolean,
                ) = b
            },
        )
    }

    @AfterEach
    fun unregister() {
        Delta.unregisterEmbed(embedType)
    }

    @Test
    fun compose() {
        val doc = Delta().insert(counter(3))
        assertEquals(Delta().insert(counter(5)), doc.compose(Delta().retain(counter(2))))
    }

    @Test
    fun invert() {
        val doc = Delta().insert(counter(3))
        val change = Delta().retain(counter(2))
        val undo = change.invert(doc)
        assertEquals(Delta().retain(counter(-2)), undo)
        assertEquals(doc, doc.compose(change).compose(undo))
    }

    @Test
    fun transform() {
        val a = Delta().retain(counter(1))
        val b = Delta().retain(counter(2))
        assertEquals(b, a.transform(b, true))
    }

    @Test
    fun `unregistered type throws`() {
        Delta.unregisterEmbed(embedType)
        assertThrows<IllegalArgumentException> {
            Delta().insert(counter(3)).compose(Delta().retain(counter(2)))
        }
    }
}
