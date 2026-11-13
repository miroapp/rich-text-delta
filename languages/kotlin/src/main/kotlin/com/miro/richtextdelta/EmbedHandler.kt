package com.miro.richtextdelta

/**
 * Composes, inverts and transforms the data of one embed type. For an embed `{"image": data}`
 * the handler registered for `"image"` receives `data`.
 */
public interface EmbedHandler<T> {
    public fun compose(
        a: T,
        b: T,
        keepNull: Boolean,
    ): T

    public fun invert(
        a: T,
        b: T,
    ): T

    public fun transform(
        a: T,
        b: T,
        priority: Boolean,
    ): T
}
