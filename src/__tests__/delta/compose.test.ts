import { Delta } from '../../Delta';
import type { Op } from '../../Op';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('compose()', () => {
  it('insert + insert', () => {
    const a = new Delta().insert('A');
    const b = new Delta().insert('B');
    const expected = new Delta().insert('B').insert('A');
    expect(a.compose(b)).toEqual(expected);
  });

  it('insert + retain', () => {
    const a = new Delta().insert('A');
    const b = new Delta().retain(1, { bold: true, color: 'red', font: null });
    const expected = new Delta().insert('A', { bold: true, color: 'red' });
    expect(a.compose(b)).toEqual(expected);
  });

  it('insert + delete', () => {
    const a = new Delta().insert('A');
    const b = new Delta().delete(1);
    const expected = new Delta();
    expect(a.compose(b)).toEqual(expected);
  });

  it('delete + insert', () => {
    const a = new Delta().delete(1);
    const b = new Delta().insert('B');
    const expected = new Delta().insert('B').delete(1);
    expect(a.compose(b)).toEqual(expected);
  });

  it('delete + retain', () => {
    const a = new Delta().delete(1);
    const b = new Delta().retain(1, { bold: true, color: 'red' });
    const expected = new Delta().delete(1).retain(1, { bold: true, color: 'red' });
    expect(a.compose(b)).toEqual(expected);
  });

  it('delete + delete', () => {
    const a = new Delta().delete(1);
    const b = new Delta().delete(1);
    const expected = new Delta().delete(2);
    expect(a.compose(b)).toEqual(expected);
  });

  it('retain + insert', () => {
    const a = new Delta().retain(1, { color: 'blue' });
    const b = new Delta().insert('B');
    const expected = new Delta().insert('B').retain(1, { color: 'blue' });
    expect(a.compose(b)).toEqual(expected);
  });

  it('retain + retain', () => {
    const a = new Delta().retain(1, { color: 'blue' });
    const b = new Delta().retain(1, { bold: true, color: 'red', font: null });
    const expected = new Delta().retain(1, {
      bold: true,
      color: 'red',
      font: null,
    });
    expect(a.compose(b)).toEqual(expected);
  });

  it('retain + delete', () => {
    const a = new Delta().retain(1, { color: 'blue' });
    const b = new Delta().delete(1);
    const expected = new Delta().delete(1);
    expect(a.compose(b)).toEqual(expected);
  });

  it('insert in middle of text', () => {
    const a = new Delta().insert('Hello');
    const b = new Delta().retain(3).insert('X');
    const expected = new Delta().insert('HelXlo');
    expect(a.compose(b)).toEqual(expected);
  });

  it('insert and delete ordering', () => {
    const a = new Delta().insert('Hello');
    const b = new Delta().insert('Hello');
    const insertFirst = new Delta().retain(3).insert('X').delete(1);
    const deleteFirst = new Delta().retain(3).delete(1).insert('X');
    const expected = new Delta().insert('HelXo');
    expect(a.compose(insertFirst)).toEqual(expected);
    expect(b.compose(deleteFirst)).toEqual(expected);
  });

  it('insert embed', () => {
    const a = new Delta().insert({ embed: 1 }, { src: 'http://quilljs.com/image.png' });
    const b = new Delta().retain(1, { alt: 'logo' });
    const expected = new Delta().insert(
      { embed: 1 },
      {
        src: 'http://quilljs.com/image.png',
        alt: 'logo',
      },
    );
    expect(a.compose(b)).toEqual(expected);
  });

  it('retain embed', () => {
    const a = new Delta().retain({ figure: true }, { src: 'http://quilljs.com/image.png' });
    const b = new Delta().retain(1, { alt: 'logo' });
    const expected = new Delta().retain(
      { figure: true },
      {
        src: 'http://quilljs.com/image.png',
        alt: 'logo',
      },
    );
    expect(a.compose(b)).toEqual(expected);
  });

  it('delete entire text', () => {
    const a = new Delta().retain(4).insert('Hello');
    const b = new Delta().delete(9);
    const expected = new Delta().delete(4);
    expect(a.compose(b)).toEqual(expected);
  });

  it('retain more than length of text', () => {
    const a = new Delta().insert('Hello');
    const b = new Delta().retain(10);
    const expected = new Delta().insert('Hello');
    expect(a.compose(b)).toEqual(expected);
  });

  it('retain empty embed', () => {
    const a = new Delta().insert({ embed: 1 });
    const b = new Delta().retain(1);
    const expected = new Delta().insert({ embed: 1 });
    expect(a.compose(b)).toEqual(expected);
  });

  it('remove all attributes', () => {
    const a = new Delta().insert('A', { bold: true });
    const b = new Delta().retain(1, { bold: null });
    const expected = new Delta().insert('A');
    expect(a.compose(b)).toEqual(expected);
  });

  it('remove all embed attributes', () => {
    const a = new Delta().insert({ embed: 2 }, { bold: true });
    const b = new Delta().retain(1, { bold: null });
    const expected = new Delta().insert({ embed: 2 });
    expect(a.compose(b)).toEqual(expected);
  });

  describe('Nested attributes', () => {
    it('add nested attributes', () => {
      const a = new Delta().insert('A');
      const b = new Delta().retain(1, { comment: { '1': true } });
      const expected = new Delta().insert('A', { comment: { '1': true } });
      expect(a.compose(b)).toEqual(expected);
    });

    it('add nested attribute to existing object', () => {
      const a = new Delta().insert('A', { comment: { '1': true } });
      const b = new Delta().retain(1, { comment: { '2': true } });
      const expected = new Delta().insert('A', {
        comment: { '1': true, '2': true },
      });
      expect(a.compose(b)).toEqual(expected);
    });

    it('remove nested attributes', () => {
      const a = new Delta().insert('A', { comment: { '1': true, '2': true } });
      const b = new Delta().retain(1, { comment: { '2': null } });
      const expected = new Delta().insert('A', { comment: { '1': true } });
      expect(a.compose(b)).toEqual(expected);
    });

    it('nested attributes splits inserts', () => {
      const a = new Delta().insert('AB', { comment: { '1': true } });
      const b = new Delta().retain(1, { comment: { '2': true } });
      const expected = new Delta()
        .insert('A', { comment: { '1': true, '2': true } })
        .insert('B', { comment: { '1': true } });
      expect(a.compose(b)).toEqual(expected);
    });

    it('nested attributes joins inserts', () => {
      const a = new Delta()
        .insert('A', { comment: { '1': true, '2': true } })
        .insert('B', { comment: { '1': true } });
      const b = new Delta().retain(1).retain(1, { comment: { '2': true } });
      const expected = new Delta().insert('AB', {
        comment: { '1': true, '2': true },
      });
      expect(a.compose(b)).toEqual(expected);
    });

    it('top level null removes all nested attributes', () => {
      const a = new Delta().insert('A', {
        suggestion: { '1': { bold: true }, '2': { underline: true } },
      });
      const b = new Delta().retain(1, { suggestion: null });
      const expected = new Delta().insert('A');
      expect(a.compose(b)).toEqual(expected);
    });

    it('removing final key in nested object removes outer key', () => {
      const a = new Delta().insert('A', {
        suggestion: { '1': { bold: true }, '2': { underline: true } },
      });
      const b = new Delta().retain(1, { suggestion: { '1': { bold: null } } });
      const expected = new Delta().insert('A', {
        suggestion: { '2': { underline: true } },
      });
      expect(a.compose(b)).toEqual(expected);
    });

    it('changes a nested value', () => {
      const a = new Delta().insert('A', { comment: { '1': 'a', '99': 'keep' } });
      const b = new Delta().retain(1, { comment: { '1': 'b' } });
      const expected = new Delta().insert('A', {
        comment: { '1': 'b', '99': 'keep' },
      });
      expect(a.compose(b)).toEqual(expected);
    });

    it('adds and removes nested keys in the same map', () => {
      const a = new Delta().insert('A', { comment: { '1': true, '99': true } });
      const b = new Delta().retain(1, { comment: { '1': null, '2': true } });
      const expected = new Delta().insert('A', {
        comment: { '2': true, '99': true },
      });
      expect(a.compose(b)).toEqual(expected);
    });

    it('no-op nested change keeps existing attributes', () => {
      const a = new Delta().insert('A', { comment: { '1': true, '99': true } });
      const b = new Delta().retain(1, { comment: { '1': true } });
      const expected = new Delta().insert('A', {
        comment: { '1': true, '99': true },
      });
      expect(a.compose(b)).toEqual(expected);
    });

    it('composes a deeply nested map change', () => {
      const a = new Delta().insert('A', {
        comment: { '1': { resolved: false, author: 'x' } },
      });
      const b = new Delta().retain(1, { comment: { '1': { resolved: true } } });
      const expected = new Delta().insert('A', {
        comment: { '1': { resolved: true, author: 'x' } },
      });
      expect(a.compose(b)).toEqual(expected);
    });

    it('composes changes across multiple independent map attributes', () => {
      const a = new Delta().insert('A', {
        comment: { '1': true },
        highlight: { a: true },
      });
      const b = new Delta().retain(1, {
        comment: { '2': true },
        highlight: { a: null },
      });
      const expected = new Delta().insert('A', {
        comment: { '1': true, '2': true },
      });
      expect(a.compose(b)).toEqual(expected);
    });

    it('composes a nested change spanning inserts where one lacks the map', () => {
      const a = new Delta().insert('A', { comment: { '1': true } }).insert('B');
      const b = new Delta().retain(2, { comment: { '2': true } });
      const expected = new Delta()
        .insert('A', { comment: { '1': true, '2': true } })
        .insert('B', { comment: { '2': true } });
      expect(a.compose(b)).toEqual(expected);
    });

    it('preserves nested null when composing two change deltas', () => {
      const a = new Delta().retain(1, { comment: { '1': true } });
      const b = new Delta().retain(1, { comment: { '1': null } });
      const expected = new Delta().retain(1, { comment: { '1': null } });
      expect(a.compose(b)).toEqual(expected);
    });

    it('does not share nested map references with the source delta', () => {
      const a = new Delta().insert('A');
      const b = new Delta().retain(1, { comment: { '1': true } });
      const composed = a.compose(b);
      (composed.ops[0].attributes!.comment as Record<string, unknown>)['2'] = true;
      expect(b.ops[0].attributes).toEqual({ comment: { '1': true } });
    });

    it('strips nested null when composing onto an insert with symmetrical nested object', () => {
      const a = new Delta().insert('A', { comment: { '1': true } });
      const b = new Delta().retain(1, { comment: { '1': null } });
      const expected = new Delta().insert('A');
      expect(a.compose(b)).toEqual(expected);
    });

    it('strips nested null when composing onto an insert with asymmetrical nested object', () => {
      const a = new Delta().insert('A');
      const b = new Delta().retain(1, { a: { b: null } });
      const expected = new Delta().insert('A');
      expect(a.compose(b)).toEqual(expected);
    });

    it('does not strip null on for shallow attributes on original delta', () => {
      const a = new Delta().insert('A', { bold: null });
      const b = new Delta().retain(1, { underline: null });
      const expected = new Delta().insert('A', { bold: null });
      expect(a.compose(b)).toEqual(expected);
    });

    it('does not strip null on deep attributes of the original delta', () => {
      const a = new Delta().insert('A', { a: { b: null } });
      const b = new Delta().retain(1, { underline: null });
      const expected = new Delta().insert('A', { a: { b: null } });
      expect(a.compose(b)).toEqual(expected);
    });
  });

  it('immutability', () => {
    const attr1 = { bold: true };
    const attr2 = { bold: true };
    const a1 = new Delta().insert('Test', attr1);
    const a2 = new Delta().insert('Test', attr1);
    const b1 = new Delta().retain(1, { color: 'red' }).delete(2);
    const b2 = new Delta().retain(1, { color: 'red' }).delete(2);
    const expected = new Delta().insert('T', { color: 'red', bold: true }).insert('t', attr1);
    expect(a1.compose(b1)).toEqual(expected);
    expect(a1).toEqual(a2);
    expect(b1).toEqual(b2);
    expect(attr1).toEqual(attr2);
  });

  it('retain start optimization', () => {
    const a = new Delta()
      .insert('A', { bold: true })
      .insert('B')
      .insert('C', { bold: true })
      .delete(1);
    const b = new Delta().retain(3).insert('D');
    const expected = new Delta()
      .insert('A', { bold: true })
      .insert('B')
      .insert('C', { bold: true })
      .insert('D')
      .delete(1);
    expect(a.compose(b)).toEqual(expected);
  });

  it('retain start optimization split', () => {
    const a = new Delta()
      .insert('A', { bold: true })
      .insert('B')
      .insert('C', { bold: true })
      .retain(5)
      .delete(1);
    const b = new Delta().retain(4).insert('D');
    const expected = new Delta()
      .insert('A', { bold: true })
      .insert('B')
      .insert('C', { bold: true })
      .retain(1)
      .insert('D')
      .retain(4)
      .delete(1);
    expect(a.compose(b)).toEqual(expected);
  });

  it('retain end optimization', () => {
    const a = new Delta().insert('A', { bold: true }).insert('B').insert('C', { bold: true });
    const b = new Delta().delete(1);
    const expected = new Delta().insert('B').insert('C', { bold: true });
    expect(a.compose(b)).toEqual(expected);
  });

  it('retain end optimization join', () => {
    const a = new Delta()
      .insert('A', { bold: true })
      .insert('B')
      .insert('C', { bold: true })
      .insert('D')
      .insert('E', { bold: true })
      .insert('F');
    const b = new Delta().retain(1).delete(1);
    const expected = new Delta()
      .insert('AC', { bold: true })
      .insert('D')
      .insert('E', { bold: true })
      .insert('F');
    expect(a.compose(b)).toEqual(expected);
  });

  describe('custom embed handler', () => {
    beforeEach(() => {
      Delta.registerEmbed<Op[]>('delta', {
        compose: (a, b) => new Delta(a).compose(new Delta(b)).ops,
        transform: (a, b, priority) => new Delta(a).transform(new Delta(b), priority).ops,
        invert: (a, b) => new Delta(a).invert(new Delta(b)).ops,
      });
    });

    afterEach(() => {
      Delta.unregisterEmbed('delta');
    });

    it('retain an embed with a number', () => {
      const a = new Delta().insert({ delta: [{ insert: 'a' }] });
      const b = new Delta().retain(1, { bold: true });
      const expected = new Delta().insert({ delta: [{ insert: 'a' }] }, { bold: true });
      expect(a.compose(b)).toEqual(expected);
    });

    it('retain a number with an embed', () => {
      const a = new Delta().retain(10, { bold: true });
      const b = new Delta().retain({ delta: [{ insert: 'b' }] });
      const expected = new Delta()
        .retain({ delta: [{ insert: 'b' }] }, { bold: true })
        .retain(9, { bold: true });
      expect(a.compose(b)).toEqual(expected);
    });

    it('retain an embed with an embed', () => {
      const a = new Delta().insert({ delta: [{ insert: 'a' }] });
      const b = new Delta().retain({ delta: [{ insert: 'b' }] });
      const expected = new Delta().insert({
        delta: [{ insert: 'ba' }],
      });
      expect(a.compose(b)).toEqual(expected);
    });

    it('keeps other delete when this op is a retain', () => {
      const a = new Delta().retain({ delta: [{ insert: 'a' }] });
      const b = new Delta().insert('\n').delete(1);
      const expected = new Delta().insert('\n').delete(1);
      expect(a.compose(b)).toEqual(expected);
    });

    it('retain an embed with a number', () => {
      const a = new Delta().insert({ delta: [{ insert: 'a' }] });
      const b = new Delta().retain(1, { bold: true });
      const expected = new Delta().insert({ delta: [{ insert: 'a' }] }, { bold: true });
      expect(a.compose(b)).toEqual(expected);
    });

    it('retain an embed with another type of embed', () => {
      const a = new Delta().insert({ delta: [{ insert: 'a' }] });
      const b = new Delta().retain({ otherdelta: [{ insert: 'b' }] });
      expect(() => {
        a.compose(b);
      }).toThrow(new Error('embed types not matched: delta != otherdelta'));
    });

    it('retain a string with an embed', () => {
      const a = new Delta().insert('a');
      const b = new Delta().retain({ delta: [{ insert: 'b' }] });
      expect(() => {
        a.compose(b);
      }).toThrow(new Error('cannot retain a string'));
    });

    it('retain embeds without a handler', () => {
      const a = new Delta().insert({ mydelta: [{ insert: 'a' }] });
      const b = new Delta().retain({ mydelta: [{ insert: 'b' }] });
      expect(() => {
        a.compose(b);
      }).toThrow(new Error('no handlers for embed type "mydelta"'));
    });
  });
});
