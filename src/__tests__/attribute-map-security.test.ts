import { describe, expect, it } from 'vitest';
import { AttributeMap } from '../AttributeMap';

/** Attribute map whose own keys are clean but whose prototype carries enumerable properties. */
function withInheritedKeys(own: Record<string, unknown>, inherited: Record<string, unknown>) {
  return Object.assign(Object.create(inherited), own) as AttributeMap;
}

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
