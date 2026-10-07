package com.miro.richtextdelta

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonEncoder
import kotlinx.serialization.json.JsonObject

/** Serializes a [Delta] as its JSON array of ops. JSON formats only. */
public object DeltaSerializer : KSerializer<Delta> {
    override val descriptor: SerialDescriptor =
        SerialDescriptor("com.miro.richtextdelta.Delta", JsonArray.serializer().descriptor)

    override fun serialize(
        encoder: Encoder,
        value: Delta,
    ) {
        jsonEncoder(encoder).encodeJsonElement(value.toJsonElement())
    }

    override fun deserialize(decoder: Decoder): Delta = Delta.fromJson(jsonDecoder(decoder).decodeJsonElement())
}

/** Serializes an [Op] as its JSON object. JSON formats only. */
public object OpSerializer : KSerializer<Op> {
    override val descriptor: SerialDescriptor =
        SerialDescriptor("com.miro.richtextdelta.Op", JsonObject.serializer().descriptor)

    override fun serialize(
        encoder: Encoder,
        value: Op,
    ) {
        jsonEncoder(encoder).encodeJsonElement(value.toJsonElement())
    }

    override fun deserialize(decoder: Decoder): Op = Op.fromJson(jsonDecoder(decoder).decodeJsonElement())
}

private fun jsonEncoder(encoder: Encoder): JsonEncoder =
    encoder as? JsonEncoder ?: throw SerializationException("rich-text-delta values can only be encoded as JSON")

private fun jsonDecoder(decoder: Decoder): JsonDecoder =
    decoder as? JsonDecoder ?: throw SerializationException("rich-text-delta values can only be decoded from JSON")
