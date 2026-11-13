package com.miro.richtextdelta

import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonNull
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertInstanceOf
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class JsonTest {
    private val json = """[{"insert":"Hi","attributes":{"bold":true}},{"insert":{"image":"cat.png"}}]"""

    @Test
    fun `fromJson and toJson round trip`() {
        val delta = Delta.fromJson(json)
        assertEquals(
            Delta().insert("Hi", mapOf("bold" to true)).insert(mapOf("image" to "cat.png")),
            delta,
        )
        assertEquals(json, delta.toJson())
        assertEquals(Json.parseToJsonElement(json), delta.toJsonElement())
        assertInstanceOf(JsonArray::class.java, delta.toJsonElement())
    }

    @Test
    fun `fromJson accepts an ops object`() {
        assertEquals(Delta.fromJson(json), Delta.fromJson("""{"ops":$json}"""))
    }

    @Test
    fun `kotlinx serialization`() {
        val delta = Delta.fromJson(json)
        assertEquals(json, Json.encodeToString(delta))
        assertEquals(Delta().retain(3), Json.decodeFromString<Delta>("""[{"retain":3}]"""))
        assertEquals(
            Op.Delete(2),
            Json.decodeFromString<Op>("""{"delete":2}"""),
        )
        assertEquals("""{"delete":2}""", Json.encodeToString<Op>(Op.Delete(2)))
    }

    @Test
    fun `op json`() {
        val op = Op.Retain(RetainLength(4, mapOf("bold" to null)))
        assertEquals("""{"retain":4,"attributes":{"bold":null}}""", op.toJson())
        assertEquals(op, Op.fromJson(op.toJson()))
        assertEquals(Op.Retain(RetainEmbed(mapOf("counter" to 1))), Op.fromJson("""{"retain":{"counter":1}}"""))
    }

    @Test
    fun `attribute map json`() {
        val attrs = mapOf("style" to mapOf("color" to "red"), "list" to listOf(1, "a"), "bold" to null)
        val encoded = AttributeMaps.toJson(attrs)
        assertEquals("""{"style":{"color":"red"},"list":[1,"a"],"bold":null}""", encoded)
        assertEquals(attrs, AttributeMaps.fromJson(encoded))
        assertNull(AttributeMaps.fromJson("null"))
        assertEquals(JsonNull, AttributeMaps.toJsonElement(null))
    }

    @Test
    fun `numbers decode as Int then Long then Double`() {
        val attrs = AttributeMaps.fromJson("""{"i":1,"l":10000000000,"d":1.5}""")!!
        assertInstanceOf(Int::class.javaObjectType, attrs["i"])
        assertInstanceOf(Long::class.javaObjectType, attrs["l"])
        assertInstanceOf(Double::class.javaObjectType, attrs["d"])
    }

    @Test
    fun `malformed json throws SerializationException`() {
        assertThrows<SerializationException> { Delta.fromJson("not json") }
        assertThrows<SerializationException> { Delta.fromJson("""{"foo":[]}""") }
        assertThrows<SerializationException> { Delta.fromJson("42") }
        assertThrows<SerializationException> { Op.fromJson("""{"bogus":1}""") }
        assertThrows<SerializationException> { AttributeMaps.fromJson("[1]") }
    }
}
