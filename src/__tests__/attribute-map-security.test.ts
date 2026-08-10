import { describe, expect, it } from 'vitest';
import { AttributeMap, MAX_NESTING_DEPTH, NestingDepthExceededError } from '../AttributeMap';

/** Attribute map whose own keys are clean but whose prototype carries enumerable properties. */
function withInheritedKeys(own: Record<string, unknown>, inherited: Record<string, unknown>) {
  return Object.assign(Object.create(inherited), own) as AttributeMap;
}

/**
 * Parsing raw JSON is the only way to build an *own* `__proto__` key: in an object
 * literal `__proto__:` sets the prototype instead, so the key never materialises.
 */
function withDangerousKeys(payload: Record<string, unknown> = { polluted: true }): AttributeMap {
  const encoded = JSON.stringify(payload);
  return JSON.parse(
    `{"bold":true,"__proto__":${encoded},"constructor":${encoded},"prototype":${encoded}}`,
  ) as AttributeMap;
}

describe('AttributeMap prototype pollution', () => {
  it.each([
    ['compose left', () => AttributeMap.compose(withDangerousKeys(), { italic: true })],
    ['compose right', () => AttributeMap.compose({ italic: true }, withDangerousKeys())],
    ['compose both', () => AttributeMap.compose(withDangerousKeys(), withDangerousKeys())],
    ['diff', () => AttributeMap.diff(withDangerousKeys(), withDangerousKeys({ other: 1 }))],
    ['invert', () => AttributeMap.invert(withDangerousKeys(), withDangerousKeys({ other: 1 }))],
    ['transform', () => AttributeMap.transform(withDangerousKeys(), withDangerousKeys(), true)],
  ])('%s neither pollutes Object.prototype nor emits dangerous keys', (_name, operation) => {
    const result = operation() ?? {};

    expect(({} as Record<string, unknown>).polluted).toBe(undefined);
    expect(Object.prototype).not.toHaveProperty('polluted');
    // Assigning `__proto__` swaps the result's prototype rather than adding a key,
    // so the own-key check below cannot detect that exploit on its own.
    expect(Object.getPrototypeOf(result)).toBe(Object.prototype);
    expect((result as Record<string, unknown>).polluted).toBe(undefined);
    for (const key of ['__proto__', 'constructor', 'prototype']) {
      expect(Object.hasOwn(result, key)).toBe(false);
    }
  });

  it('sanity check: the fixture really carries an own __proto__ key', () => {
    expect(Object.keys(withDangerousKeys())).toContain('__proto__');
  });

  it('strips dangerous keys nested inside a composed value', () => {
    const b = { meta: withDangerousKeys() };

    const result = AttributeMap.compose({ bold: true }, b) as { meta: AttributeMap };

    expect(result.meta).toEqual({ bold: true });
    expect(Object.hasOwn(result.meta, '__proto__')).toBe(false);
    expect(Object.getPrototypeOf(result.meta)).toBe(Object.prototype);
  });

  it('strips dangerous keys nested inside arrays', () => {
    const b = { items: [withDangerousKeys()] };

    const result = AttributeMap.compose({}, b) as { items: AttributeMap[] };

    expect(result.items).toEqual([{ bold: true }]);
    expect(Object.hasOwn(result.items[0], '__proto__')).toBe(false);
    expect(Object.getPrototypeOf(result.items[0])).toBe(Object.prototype);
  });

  it('does not merge a dangerous key even when both sides nest it', () => {
    const a = withDangerousKeys({ isAdmin: false });
    const b = withDangerousKeys({ isAdmin: true });

    AttributeMap.compose(a, b);

    expect(({} as Record<string, unknown>).isAdmin).toBe(undefined);
  });

  it('keeps deep-cloning composed values so the input is not shared', () => {
    const nested = { bold: true };

    const result = AttributeMap.compose({}, { meta: nested }) as { meta: AttributeMap };

    expect(result.meta).toEqual(nested);
    expect(result.meta).not.toBe(nested);
  });
});

describe('AttributeMap own-key enumeration', () => {
  it('compose ignores inherited enumerable keys on the left', () => {
    const a = withInheritedKeys({ bold: true }, { injected: 'from-prototype' });

    expect(AttributeMap.compose(a, {})).toEqual({ bold: true });
  });

  it('compose ignores inherited enumerable keys on the right', () => {
    const b = withInheritedKeys({ italic: true }, { injected: 'from-prototype' });

    expect(AttributeMap.compose({}, b)).toEqual({ italic: true });
  });

  it('diff ignores inherited enumerable keys', () => {
    const a = withInheritedKeys({ bold: true }, { injected: 'x' });
    const b = withInheritedKeys({ bold: true }, { injected: 'y' });

    expect(AttributeMap.diff(a, b)).toBe(undefined);
  });

  it('invert ignores inherited enumerable keys', () => {
    const attr = withInheritedKeys({ bold: true }, { injected: 'x' });
    const base = withInheritedKeys({}, { injected: 'y' });

    expect(AttributeMap.invert(attr, base)).toEqual({ bold: null });
  });

  it('transform ignores inherited enumerable keys', () => {
    const a = withInheritedKeys({}, { injected: 'x' });
    const b = withInheritedKeys({ italic: true }, { injected: 'y' });

    expect(AttributeMap.transform(a, b, true)).toEqual({ italic: true });
  });

  it('does not recurse into values with a custom prototype', () => {
    const a = { meta: withInheritedKeys({ bold: true }, { injected: 'x' }) };
    const b = { meta: withInheritedKeys({ italic: true }, { injected: 'y' }) };

    // Treated as an opaque leaf, so `b` wins outright rather than being merged.
    expect(AttributeMap.compose(a, b)).toEqual({ meta: b.meta });
  });

  it('non-enumerable own properties are never processed', () => {
    const a: AttributeMap = { bold: true };
    Object.defineProperty(a, 'hidden', { value: 'secret', enumerable: false });

    expect(AttributeMap.compose(a, {})).toEqual({ bold: true });
  });

  it('still recurses into plain nested maps', () => {
    expect(AttributeMap.compose({ meta: { bold: true } }, { meta: { italic: true } })).toEqual({
      meta: { bold: true, italic: true },
    });
  });
});

/** Builds `{nested: {nested: ... {leaf: value}}}` at the requested depth. */
function nest(levels: number, leaf: Record<string, unknown>): AttributeMap {
  let current: AttributeMap = leaf;
  for (let i = 0; i < levels; i++) {
    current = { nested: current };
  }
  return current;
}

describe('AttributeMap recursion depth', () => {
  const DEEP = 100_000;

  it.each([
    [
      'compose',
      () => AttributeMap.compose(nest(DEEP, { bold: true }), nest(DEEP, { italic: true })),
    ],
    [
      'compose keepNull',
      () => AttributeMap.compose(nest(DEEP, { bold: true }), nest(DEEP, { italic: null }), true),
    ],
    ['diff', () => AttributeMap.diff(nest(DEEP, { bold: true }), nest(DEEP, { bold: false }))],
    ['invert', () => AttributeMap.invert(nest(DEEP, { bold: true }), nest(DEEP, { bold: false }))],
    [
      'transform',
      () => AttributeMap.transform(nest(DEEP, { bold: true }), nest(DEEP, { italic: true }), true),
    ],
  ])('%s rejects adversarially deep input with an explicit error', (_name, operation) => {
    expect(operation).toThrow(NestingDepthExceededError);
    // The guard must fire before the stack is exhausted, not as a symptom of it.
    expect(operation).not.toThrow(RangeError);
  });

  it('merges nested maps right up to the depth bound', () => {
    const a = nest(MAX_NESTING_DEPTH - 1, { bold: true });
    const b = nest(MAX_NESTING_DEPTH - 1, { italic: true });

    expect(AttributeMap.compose(a, b)).toEqual(
      nest(MAX_NESTING_DEPTH - 1, { bold: true, italic: true }),
    );
  });

  it('rejects nesting one level past the bound rather than truncating the merge', () => {
    const a = nest(MAX_NESTING_DEPTH + 1, { bold: true });
    const b = nest(MAX_NESTING_DEPTH + 1, { italic: true });

    expect(() => AttributeMap.compose(a, b)).toThrow(NestingDepthExceededError);
  });

  it('rejects a deeply nested value while cloning it', () => {
    expect(() => AttributeMap.compose({}, { meta: nest(DEEP, { bold: true }) })).toThrow(
      NestingDepthExceededError,
    );
  });

  it('rejects deeply nested arrays', () => {
    let deep: unknown = [1];
    for (let i = 0; i < DEEP; i++) {
      deep = [deep];
    }

    expect(() => AttributeMap.compose({}, { items: deep as unknown[] })).toThrow(
      NestingDepthExceededError,
    );
  });

  it('reports the bound in the error message', () => {
    expect(() => AttributeMap.compose(nest(30, {}), nest(30, {}))).toThrow(
      /exceeds the maximum depth of 20/,
    );
  });
});
