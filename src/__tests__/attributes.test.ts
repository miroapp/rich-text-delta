import { AttributeMap, NestingDepthExceededError } from '../AttributeMap';
import { describe, it, expect, afterEach } from 'vitest';

describe('AttributeMap', () => {
  describe('compose()', () => {
    const attributes = { bold: true, color: 'red' };

    it('left is undefined', () => {
      expect(AttributeMap.compose(undefined, attributes)).toEqual(attributes);
    });

    it('right is undefined', () => {
      expect(AttributeMap.compose(attributes, undefined)).toEqual(attributes);
    });

    it('both are undefined', () => {
      expect(AttributeMap.compose(undefined, undefined)).toBe(undefined);
    });

    it('missing', () => {
      expect(AttributeMap.compose(attributes, { italic: true })).toEqual({
        bold: true,
        italic: true,
        color: 'red',
      });
    });

    it('overwrite', () => {
      expect(AttributeMap.compose(attributes, { bold: false, color: 'blue' })).toEqual({
        bold: false,
        color: 'blue',
      });
    });

    it('remove', () => {
      expect(AttributeMap.compose(attributes, { bold: null })).toEqual({
        color: 'red',
      });
    });

    it('remove to none', () => {
      expect(AttributeMap.compose(attributes, { bold: null, color: null })).toEqual(undefined);
    });

    it('remove missing', () => {
      expect(AttributeMap.compose(attributes, { italic: null })).toEqual(attributes);
    });
  });

  describe('diff()', () => {
    const format = { bold: true, color: 'red' };

    it('left is undefined', () => {
      expect(AttributeMap.diff(undefined, format)).toEqual(format);
    });

    it('right is undefined', () => {
      const expected = { bold: null, color: null };
      expect(AttributeMap.diff(format, undefined)).toEqual(expected);
    });

    it('same format', () => {
      expect(AttributeMap.diff(format, format)).toEqual(undefined);
    });

    it('add format', () => {
      const added = { bold: true, italic: true, color: 'red' };
      const expected = { italic: true };
      expect(AttributeMap.diff(format, added)).toEqual(expected);
    });

    it('remove format', () => {
      const removed = { bold: true };
      const expected = { color: null };
      expect(AttributeMap.diff(format, removed)).toEqual(expected);
    });

    it('overwrite format', () => {
      const overwritten = { bold: true, color: 'blue' };
      const expected = { color: 'blue' };
      expect(AttributeMap.diff(format, overwritten)).toEqual(expected);
    });
  });

  describe('invert()', () => {
    it('attributes is undefined', () => {
      const base = { bold: true };
      expect(AttributeMap.invert(undefined, base)).toEqual({});
    });

    it('base is undefined', () => {
      const attributes = { bold: true };
      const expected = { bold: null };
      expect(AttributeMap.invert(attributes, undefined)).toEqual(expected);
    });

    it('both undefined', () => {
      expect(AttributeMap.invert()).toEqual({});
    });

    it('merge', () => {
      const attributes = { bold: true };
      const base = { italic: true };
      const expected = { bold: null };
      expect(AttributeMap.invert(attributes, base)).toEqual(expected);
    });

    it('null', () => {
      const attributes = { bold: null };
      const base = { bold: true };
      const expected = { bold: true };
      expect(AttributeMap.invert(attributes, base)).toEqual(expected);
    });

    it('replace', () => {
      const attributes = { color: 'red' };
      const base = { color: 'blue' };
      const expected = base;
      expect(AttributeMap.invert(attributes, base)).toEqual(expected);
    });

    it('noop', () => {
      const attributes = { color: 'red' };
      const base = { color: 'red' };
      const expected = {};
      expect(AttributeMap.invert(attributes, base)).toEqual(expected);
    });

    it('combined', () => {
      const attributes = {
        bold: true,
        italic: null,
        color: 'red',
        size: '12px',
      };
      const base = { font: 'serif', italic: true, color: 'blue', size: '12px' };
      const expected = { bold: null, italic: true, color: 'blue' };
      expect(AttributeMap.invert(attributes, base)).toEqual(expected);
    });
  });

  describe('array values (atomic, last-write-wins)', () => {
    it('compose overwrites the whole array', () => {
      expect(AttributeMap.compose({ ids: [1, 2] }, { ids: [3] })).toEqual({
        ids: [3],
      });
    });

    it('compose keeps an array untouched by the other side', () => {
      expect(AttributeMap.compose({ ids: [1, 2] }, { other: true })).toEqual({
        ids: [1, 2],
        other: true,
      });
    });

    it('diff yields the whole new array', () => {
      expect(AttributeMap.diff({ ids: [1, 2] }, { ids: [3] })).toEqual({
        ids: [3],
      });
    });

    it('diff of equal arrays is a no-op', () => {
      expect(AttributeMap.diff({ ids: [1, 2] }, { ids: [1, 2] })).toEqual(undefined);
    });

    it('invert restores the base array', () => {
      expect(AttributeMap.invert({ ids: [3] }, { ids: [1, 2] })).toEqual({
        ids: [1, 2],
      });
    });

    it('transform with priority drops the other array', () => {
      expect(AttributeMap.transform({ ids: [1, 2] }, { ids: [3] }, true)).toEqual(undefined);
    });

    it('transform without priority keeps the other array', () => {
      expect(AttributeMap.transform({ ids: [1, 2] }, { ids: [3] }, false)).toEqual({ ids: [3] });
    });
  });

  describe('transform()', () => {
    const left = { bold: true, color: 'red', font: null };
    const right = { color: 'blue', font: 'serif', italic: true };

    it('left is undefined', () => {
      expect(AttributeMap.transform(undefined, left, false)).toEqual(left);
    });

    it('right is undefined', () => {
      expect(AttributeMap.transform(left, undefined, false)).toEqual(undefined);
    });

    it('both are undefined', () => {
      expect(AttributeMap.transform(undefined, undefined, false)).toEqual(undefined);
    });

    it('with priority', () => {
      expect(AttributeMap.transform(left, right, true)).toEqual({
        italic: true,
      });
    });

    it('without priority', () => {
      expect(AttributeMap.transform(left, right, false)).toEqual(right);
    });
  });

  describe('recursion depth', () => {
    function nest(levels: number, leaf: AttributeMap): AttributeMap {
      let out: AttributeMap = leaf;
      for (let i = 0; i < levels; i++) {
        out = { n: out };
      }
      return out;
    }

    describe('compose()', () => {
      const a = { x: { y: { keep: 1 } } };
      const b = { x: { y: { other: 2 } } };

      it('merges every level by default', () => {
        expect(AttributeMap.compose(a, b)).toEqual({
          x: { y: { keep: 1, other: 2 } },
        });
      });

      it('throws instead of silently truncating once the depth budget runs out', () => {
        // 'x' -> 'y' is two levels deep; a budget of 2 is exhausted right as 'y' is
        // reached, so rather than let one side win the subtree wholesale (which would
        // skip filtering it), compose rejects the input.
        expect(() => AttributeMap.compose(a, b, false, 2)).toThrow(NestingDepthExceededError);
      });

      it('throws at a depth of one when nested maps exist on both sides', () => {
        expect(() => AttributeMap.compose(a, b, false, 1)).toThrow(NestingDepthExceededError);
      });

      it('throws when composing a circular attribute map with keepNull true', () => {
        // A true cycle never bottoms out into a leaf-only structure, so no finite depth
        // budget lets it fully resolve - it always ends up needing to descend into a
        // nested map one level past the budget. Throwing is the only safe outcome;
        // silently returning some partially-cloned snapshot would be misleading.
        const a: AttributeMap = { x: 1 };
        const b: AttributeMap = { y: 1 };
        a.refToB = b;
        b.refToA = a;

        expect(() => AttributeMap.compose(a, b, true)).toThrow(NestingDepthExceededError);
      });

      it('throws when composing a circular attribute map with keepNull false', () => {
        const a: AttributeMap = { x: 1 };
        const b: AttributeMap = { y: 1 };
        a.b = b;
        b.a = a;

        expect(() => AttributeMap.compose(a, b, false)).toThrow(NestingDepthExceededError);
      });

      it('throws instead of silently truncating overly deep nesting', () => {
        expect(() =>
          AttributeMap.compose(nest(50, { bold: true }), nest(50, { italic: true }), false, 5),
        ).toThrow(NestingDepthExceededError);
      });

      it('honours the depth for null-stripping, consistently across adjacent budgets', () => {
        const d = { x: { y: null } };
        // Both budgets are enough to fully reach and strip the null two levels down -
        // there's no longer an off-by-one where a smaller budget accidentally preserves it.
        expect(AttributeMap.compose({}, d, false, 2)).toEqual(undefined);
        expect(AttributeMap.compose({}, d, false, 3)).toEqual(undefined);
      });
    });

    describe('diff()', () => {
      const a = { x: { y: { same: 1, gone: 2 } } };
      const b = { x: { y: { same: 1 } } };

      it('diffs every level by default', () => {
        expect(AttributeMap.diff(a, b)).toEqual({ x: { y: { gone: null } } });
      });

      it('yields the whole subtree once the depth budget runs out', () => {
        expect(AttributeMap.diff(a, b, 2)).toEqual({ x: { y: { same: 1 } } });
      });
    });

    describe('invert()', () => {
      const attr = { x: { y: { a: 2, b: 3 } } };
      const base = { x: { y: { a: 1 } } };

      it('inverts every level by default', () => {
        expect(AttributeMap.invert(attr, base)).toEqual({
          x: { y: { a: 1, b: null } },
        });
      });

      it('restores the whole base subtree once the depth budget runs out', () => {
        expect(AttributeMap.invert(attr, base, 2)).toEqual({ x: { y: { a: 1 } } });
      });

      it('terminates on nesting deeper than the budget', () => {
        expect(
          AttributeMap.invert(nest(50, { bold: true }), nest(50, { italic: true }), 5),
        ).toBeDefined();
      });
    });

    describe('transform()', () => {
      const a = { x: { y: { p: 1 } } };
      const b = { x: { y: { q: 2 } } };

      it('transforms every level by default', () => {
        expect(AttributeMap.transform(a, b, true)).toEqual({ x: { y: { q: 2 } } });
      });

      it('drops the other subtree once the depth budget runs out', () => {
        expect(AttributeMap.transform(a, b, true, 2)).toEqual(undefined);
      });

      it('a budget matching the nesting behaves like no budget', () => {
        expect(AttributeMap.transform(a, b, true, 3)).toEqual({ x: { y: { q: 2 } } });
      });

      it('returns the other side untouched without priority, whatever the budget', () => {
        expect(AttributeMap.transform(a, b, false, 1)).toBe(b);
      });

      it('returns the other side untouched without priority, arguments flipped', () => {
        expect(AttributeMap.transform(b, a, false, 1)).toBe(a);
      });

      it('transforms every level with the arguments flipped', () => {
        expect(AttributeMap.transform(b, a, true)).toEqual({ x: { y: { p: 1 } } });
      });

      it('drops the other subtree with the arguments flipped', () => {
        expect(AttributeMap.transform(b, a, true, 2)).toEqual(undefined);
      });

      it('keeps shallow siblings of a subtree the budget cut off', () => {
        const left = { deep: { y: { p: 1 } } };
        const right = { deep: { y: { q: 2 } }, extra: true };
        expect(AttributeMap.transform(left, right, true)).toEqual({
          deep: { y: { q: 2 } },
          extra: true,
        });
        expect(AttributeMap.transform(left, right, true, 2)).toEqual({ extra: true });
      });

      describe('with overlapping nested keys', () => {
        const left = { x: { y: { shared: 'left', onlyLeft: 1 } } };
        const right = { x: { y: { shared: 'right', onlyRight: 2 } } };

        it('keeps only the other side exclusive keys', () => {
          expect(AttributeMap.transform(left, right, true)).toEqual({
            x: { y: { onlyRight: 2 } },
          });
        });

        it('keeps the opposite exclusive keys with the arguments flipped', () => {
          expect(AttributeMap.transform(right, left, true)).toEqual({
            x: { y: { onlyLeft: 1 } },
          });
        });

        it('drops both directions once the depth budget runs out', () => {
          expect(AttributeMap.transform(left, right, true, 2)).toEqual(undefined);
          expect(AttributeMap.transform(right, left, true, 2)).toEqual(undefined);
        });

        it('is unaffected by the budget without priority', () => {
          expect(AttributeMap.transform(left, right, false, 2)).toBe(right);
          expect(AttributeMap.transform(right, left, false, 2)).toBe(left);
        });
      });
    });
  });

  describe('prototype pollution', () => {
    // JSON.parse is the only way to get an own '__proto__' key: an object literal
    // would set the prototype instead. This is how an attribute map arrives over
    // the wire, so it is the realistic attack shape.
    const evil = (): AttributeMap => JSON.parse('{"__proto__": {"polluted": true}}');
    const nestedEvil = (): AttributeMap =>
      JSON.parse('{"outer": {"__proto__": {"polluted": true}, "underline": true}}');
    const globalProto = Object.prototype as unknown as Record<string, unknown>;

    afterEach(() => {
      delete globalProto.polluted;
    });

    function expectNotPolluted(value: unknown) {
      expect((value as AttributeMap)?.polluted).toBeUndefined();
      expect(Object.getPrototypeOf(value)).toBe(Object.prototype);
    }

    describe('compose()', () => {
      it('leaves Object.prototype untouched for a nested __proto__ on the right', () => {
        const res = AttributeMap.compose({ outer: { bold: true } }, nestedEvil());
        expect((res as any).outer.bold).toBe(true);
        expect((res as any).outer!.underline).toBe(true);
        expectNotPolluted((res as any).outer);
        expect(globalProto.polluted).toBeUndefined();
      });

      it('leaves Object.prototype untouched for a nested __proto__ on the left', () => {
        const res = AttributeMap.compose(nestedEvil(), { outer: { bold: true } });
        expect(globalProto.polluted).toBeUndefined();
        expect((res as any).outer.bold).toBe(true);
        expect((res as any).outer!.underline).toBe(true);
        expectNotPolluted((res as any).outer);
      });

      it('does not remove existing __proto__ objects on the document', () => {
        // this test documents the fact that the algorithm does not scan unaffected attributes for pollution
        const res = AttributeMap.compose(nestedEvil(), { bold: true });
        expect(globalProto.polluted).toBeUndefined();
        expect((res as any).outer!.underline).toBe(true);
        expect((res as any).outer!.__proto__.polluted).toBe(true);
      });

      it('leaves Object.prototype untouched when both sides nest __proto__', () => {
        const res = AttributeMap.compose(nestedEvil(), nestedEvil());
        expect(globalProto.polluted).toBeUndefined();
        expect((res as any).outer!.underline).toBe(true);
        expectNotPolluted((res as any).outer);
      });

      it('leaves Object.prototype untouched for a top-level __proto__', () => {
        expect(AttributeMap.compose({ bold: true }, evil())).toStrictEqual({ bold: true });
        expect(AttributeMap.compose(evil(), { bold: true })).toStrictEqual({ bold: true });
        expect(globalProto.polluted).toBeUndefined();
      });

      it('leaves Object.prototype untouched when keeping nulls', () => {
        const res = AttributeMap.compose({ outer: { bold: true } }, nestedEvil(), true);
        expect((res as any).outer.bold).toBe(true);
        expect((res as any).outer!.underline).toBe(true);
        expectNotPolluted((res as any).outer);

        expect(globalProto.polluted).toBeUndefined();
      });

      it('throws rather than leaking a __proto__ attack buried past the depth budget', () => {
        const levels = 150;
        const deeplyNestedEvil = JSON.parse(
          '{"n":'.repeat(levels) +
            '{"__proto__": {"polluted": true}, "leaf": true}' +
            '}'.repeat(levels),
        );

        expect(() => AttributeMap.compose({}, deeplyNestedEvil)).toThrow(
          NestingDepthExceededError,
        );
        expect(globalProto.polluted).toBeUndefined();
      });

      it('does not surface injected keys as attributes of the result', () => {
        const composed = AttributeMap.compose({ outer: { bold: true } }, nestedEvil());
        const outer = composed?.outer as AttributeMap;
        expect(Object.keys(composed ?? {})).toEqual(['outer']);
        expect(Object.keys(outer).sort()).toEqual(['bold', 'underline']);
        expect(outer.bold).toBe(true);
        expect(outer.underline).toBe(true);
      });

      it('does not let a nested __proto__ leak onto the result via inheritance', () => {
        const composed = AttributeMap.compose({ outer: { bold: true } }, nestedEvil());
        const outer = composed?.outer as AttributeMap;
        expect(outer.bold).toBe(true);
        expect(outer.underline).toBe(true);
        expectNotPolluted(outer);
      });

      it('does not leak when only one side carries the nested subtree', () => {
        // The subtree is copied wholesale rather than composed key by key,
        // but the copy still strips __proto__ via safeKeys, so 'underline' survives
        // and no pollution leaks through.
        const composed = AttributeMap.compose({ bold: true }, nestedEvil());
        const outer = composed?.outer as AttributeMap;
        expect(composed?.bold).toBe(true);
        expect(outer.underline).toBe(true);
        expectNotPolluted(outer);
      });

      it('does not leak when only one side carries the nested subtree, arguments flipped', () => {
        const composed = AttributeMap.compose(nestedEvil(), { bold: true });
        const outer = composed?.outer as AttributeMap;
        expect(composed?.bold).toBe(true);
        expect(outer.underline).toBe(true);
        expectNotPolluted(outer);
      });

      it('does not leak through a __proto__ nested inside an array value', () => {
        const composed = AttributeMap.compose(
          { bold: true },
          JSON.parse('{"ids": [{"__proto__": {"polluted": true}}]}'),
        );
        expect((composed as AttributeMap).bold).toBe(true);
        const [first] = (composed as AttributeMap).ids as AttributeMap[];
        expectNotPolluted(first);
      });

      it('ignores a top-level __proto__ attribute entirely', () => {
        const composed = AttributeMap.compose({ bold: true }, evil());
        expect(composed).toEqual({ bold: true });
        expectNotPolluted(composed);
      });
    });

    describe('diff()', () => {
      it('leaves Object.prototype untouched', () => {
        AttributeMap.diff({ outer: { bold: true } }, nestedEvil());
        AttributeMap.diff(nestedEvil(), { outer: { bold: true } });
        expect(globalProto.polluted).toBeUndefined();
      });

      it('does not let a top-level __proto__ leak onto the result', () => {
        const diffed = AttributeMap.diff({ bold: true }, evil()) as AttributeMap;
        expect(diffed).toEqual({ bold: null });
        expectNotPolluted(diffed);
      });

      it('ignores a nested __proto__ on either side', () => {
        // 'underline' is a real attribute difference, not injected pollution -
        // it legitimately appears since only one side has it.
        const leftToRight = AttributeMap.diff(
          { outer: { bold: true } },
          nestedEvil(),
        ) as AttributeMap;
        expect(leftToRight).toEqual({ outer: { bold: null, underline: true } });
        expectNotPolluted(leftToRight.outer);

        const rightToLeft = AttributeMap.diff(nestedEvil(), {
          outer: { bold: true },
        }) as AttributeMap;
        expect(rightToLeft).toEqual({ outer: { underline: null, bold: true } });
        expectNotPolluted(rightToLeft.outer);
      });
    });
  });
});
