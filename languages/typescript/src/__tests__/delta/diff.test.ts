import { Delta } from '../../Delta';
import { describe, it, expect } from 'vitest';

describe('diff()', () => {
  it('insert', () => {
    const a = new Delta().insert('A');
    const b = new Delta().insert('AB');
    const expected = new Delta().retain(1).insert('B');
    expect(a.diff(b)).toEqual(expected);
  });

  it('delete', () => {
    const a = new Delta().insert('AB');
    const b = new Delta().insert('A');
    const expected = new Delta().retain(1).delete(1);
    expect(a.diff(b)).toEqual(expected);
  });

  it('retain', () => {
    const a = new Delta().insert('A');
    const b = new Delta().insert('A');
    const expected = new Delta();
    expect(a.diff(b)).toEqual(expected);
  });

  it('format', () => {
    const a = new Delta().insert('A');
    const b = new Delta().insert('A', { bold: true });
    const expected = new Delta().retain(1, { bold: true });
    expect(a.diff(b)).toEqual(expected);
  });

  it('object attributes', () => {
    const a = new Delta().insert('A', {
      font: { family: 'Helvetica', size: '15px' },
    });
    const b = new Delta().insert('A', {
      font: { family: 'Helvetica', size: '15px' },
    });
    const expected = new Delta();
    expect(a.diff(b)).toEqual(expected);
  });

  it('embed integer match', () => {
    const a = new Delta().insert({ embed: 1 });
    const b = new Delta().insert({ embed: 1 });
    const expected = new Delta();
    expect(a.diff(b)).toEqual(expected);
  });

  it('embed integer mismatch', () => {
    const a = new Delta().insert({ embed: 1 });
    const b = new Delta().insert({ embed: 2 });
    const expected = new Delta().delete(1).insert({ embed: 2 });
    expect(a.diff(b)).toEqual(expected);
  });

  it('embed object match', () => {
    const a = new Delta().insert({ image: 'http://quilljs.com' });
    const b = new Delta().insert({ image: 'http://quilljs.com' });
    const expected = new Delta();
    expect(a.diff(b)).toEqual(expected);
  });

  it('embed object mismatch', () => {
    const a = new Delta().insert({
      image: 'http://quilljs.com',
      alt: 'Overwrite',
    });
    const b = new Delta().insert({ image: 'http://quilljs.com' });
    const expected = new Delta().insert({ image: 'http://quilljs.com' }).delete(1);
    expect(a.diff(b)).toEqual(expected);
  });

  it('embed object change', () => {
    const embed = { image: 'http://quilljs.com' };
    const a = new Delta().insert(embed);
    embed.image = 'http://github.com';
    const b = new Delta().insert(embed);
    const expected = new Delta().insert({ image: 'http://github.com' }).delete(1);
    expect(a.diff(b)).toEqual(expected);
  });

  it('embed false positive', () => {
    const a = new Delta().insert({ embed: 1 });
    const b = new Delta().insert(String.fromCharCode(0)); // Placeholder char for embed in diff()
    const expected = new Delta().insert(String.fromCharCode(0)).delete(1);
    expect(a.diff(b)).toEqual(expected);
  });

  it('error on non-documents', () => {
    const a = new Delta().insert('A');
    const b = new Delta().retain(1).insert('B');
    expect(() => {
      a.diff(b);
    }).toThrow();
    expect(() => {
      b.diff(a);
    }).toThrow();
  });

  it('inconvenient indexes', () => {
    const a = new Delta().insert('12', { bold: true }).insert('34', { italic: true });
    const b = new Delta().insert('123', { color: 'red' });
    const expected = new Delta()
      .retain(2, { bold: null, color: 'red' })
      .retain(1, { italic: null, color: 'red' })
      .delete(1);
    expect(a.diff(b)).toEqual(expected);
  });

  it('combination', () => {
    const a = new Delta().insert('Bad', { color: 'red' }).insert('cat', { color: 'blue' });
    const b = new Delta().insert('Good', { bold: true }).insert('dog', { italic: true });
    const expected = new Delta()
      .insert('Good', { bold: true })
      .insert('dog', { italic: true })
      .delete(6);
    expect(a.diff(b)).toEqual(expected);
  });

  it('same document', () => {
    const a = new Delta().insert('A').insert('B', { bold: true });
    const expected = new Delta();
    expect(a.diff(a)).toEqual(expected);
  });

  it('immutability', () => {
    const attr1 = { color: 'red' };
    const attr2 = { color: 'red' };
    const a1 = new Delta().insert('A', attr1);
    const a2 = new Delta().insert('A', attr1);
    const b1 = new Delta().insert('A', { bold: true }).insert('B');
    const b2 = new Delta().insert('A', { bold: true }).insert('B');
    const expected = new Delta().retain(1, { bold: true, color: null }).insert('B');
    expect(a1.diff(b1)).toEqual(expected);
    expect(a1).toEqual(a2);
    expect(b2).toEqual(b2);
    expect(attr1).toEqual(attr2);
  });

  it('non-document', () => {
    const a = new Delta().insert('Test');
    const b = new Delta().delete(4);
    expect(() => {
      a.diff(b);
    }).toThrow(new Error('diff() called on non-document'));
  });

  describe('nested attributes', () => {
    it('diffs adding a nested attribute', () => {
      const a = new Delta().insert('A');
      const b = new Delta().insert('A', { comment: { '1': true } });
      const expected = new Delta().retain(1, { comment: { '1': true } });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('diffs adding multiple nested attributes', () => {
      const a = new Delta().insert('A');
      const b = new Delta().insert('A', { comment: { '1': true, '2': true } });
      const expected = new Delta().retain(1, {
        comment: { '1': true, '2': true },
      });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('diffs adding a nested attribute to an existing map', () => {
      const a = new Delta().insert('A', { comment: { '1': true, '99': true } });
      const b = new Delta().insert('A', {
        comment: { '1': true, '99': true, '2': true },
      });
      const expected = new Delta().retain(1, { comment: { '2': true } });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('diffs removing a nested attribute', () => {
      const a = new Delta().insert('A', { comment: { '1': true } });
      const b = new Delta().insert('A');
      const expected = new Delta().retain(1, { comment: null });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('diffs removing a nested attribute from an existing map', () => {
      const a = new Delta().insert('A', { comment: { '1': true, '2': true } });
      const b = new Delta().insert('A', { comment: { '1': true } });
      const expected = new Delta().retain(1, { comment: { '2': null } });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('diffs changing a nested value', () => {
      const a = new Delta().insert('A', { comment: { '1': 'a', '99': 'c' } });
      const b = new Delta().insert('A', { comment: { '1': 'b', '99': 'c' } });
      const expected = new Delta().retain(1, { comment: { '1': 'b' } });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('diffs adding and removing nested keys in the same map', () => {
      const a = new Delta().insert('A', { comment: { '1': true, '99': true } });
      const b = new Delta().insert('A', { comment: { '2': true, '99': true } });
      const expected = new Delta().retain(1, {
        comment: { '1': null, '2': true },
      });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('diffs a no-op nested change', () => {
      const a = new Delta().insert('A', { comment: { '1': true, '99': true } });
      const b = new Delta().insert('A', { comment: { '1': true, '99': true } });
      const expected = new Delta();
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('diffs a deeply nested map change', () => {
      const a = new Delta().insert('A', {
        comment: { '1': { resolved: false, author: 'x' } },
      });
      const b = new Delta().insert('A', {
        comment: { '1': { resolved: true, author: 'x' } },
      });
      const expected = new Delta().retain(1, {
        comment: { '1': { resolved: true } },
      });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('diffs changes across multiple independent map attributes', () => {
      const a = new Delta().insert('A', {
        comment: { '1': true },
        highlight: { a: true, b: true },
      });
      const b = new Delta().insert('A', {
        comment: { '1': true, '2': true },
        highlight: { b: true },
      });
      const expected = new Delta().retain(1, {
        comment: { '2': true },
        highlight: { a: null },
      });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });

    it('nested attributes with the value undefined are ignored by diff', () => {
      const a = new Delta().insert('A', { comment: { '1': true } });
      const b = new Delta().insert('A', {
        comment: { '1': true, '2': undefined },
      });
      const diffed = a.diff(b);
      const expected = new Delta();
      expect(diffed).toStrictEqual(expected);
      expect(a.compose(diffed)).toEqual(a);
    });

    it('nested attributes with the value null are not ignored by diff', () => {
      const a = new Delta().insert('A', { comment: { '1': true } });
      const b = new Delta().insert('A', {
        comment: { '1': true, '2': null },
      });
      const diffed = a.diff(b);
      const expected = new Delta().retain(1, { comment: { '2': null } });
      expect(diffed).toStrictEqual(expected);
      // null attribute values on inserts are removed by compose
      expect(a.compose(diffed)).toEqual(new Delta().insert('A', { comment: { '1': true } }));
    });

    it('diffs a nested change spanning inserts', () => {
      const a = new Delta().insert('A', { comment: { '1': true, '99': true } }).insert('B');
      const b = new Delta()
        .insert('A', { comment: { '1': true } })
        .insert('B', { comment: { '2': true } });
      const expected = new Delta()
        .retain(1, { comment: { '99': null } })
        .retain(1, { comment: { '2': true } });
      const diffed = a.diff(b);
      expect(expected).toEqual(diffed);
      expect(a.compose(diffed)).toEqual(b);
    });
  });
});
