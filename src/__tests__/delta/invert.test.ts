import {Delta} from '../../Delta'
import type {Op} from '../../Op'
import { describe, it, expect, beforeEach, afterEach } from 'vitest'

describe('invert()', () => {
	it('insert', () => {
		const delta = new Delta().retain(2).insert('A')
		const base = new Delta().insert('123456')
		const expected = new Delta().retain(2).delete(1)
		const inverted = delta.invert(base)
		expect(expected).toEqual(inverted)
		expect(base.compose(delta).compose(inverted)).toEqual(base)
	})

	it('delete', () => {
		const delta = new Delta().retain(2).delete(3)
		const base = new Delta().insert('123456')
		const expected = new Delta().retain(2).insert('345')
		const inverted = delta.invert(base)
		expect(expected).toEqual(inverted)
		expect(base.compose(delta).compose(inverted)).toEqual(base)
	})

	it('retain', () => {
		const delta = new Delta().retain(2).retain(3, {bold: true})
		const base = new Delta().insert('123456')
		const expected = new Delta().retain(2).retain(3, {bold: null})
		const inverted = delta.invert(base)
		expect(expected).toEqual(inverted)
		expect(base.compose(delta).compose(inverted)).toEqual(base)
	})

	it('retain on a delta with different attributes', () => {
		const base = new Delta().insert('123').insert('4', {bold: true})
		const delta = new Delta().retain(4, {italic: true})
		const expected = new Delta().retain(4, {italic: null})
		const inverted = delta.invert(base)
		expect(expected).toEqual(inverted)
		expect(base.compose(delta).compose(inverted)).toEqual(base)
	})

	it('combined', () => {
		const delta = new Delta()
			.retain(2)
			.delete(2)
			.insert('AB', {italic: true})
			.retain(2, {italic: null, bold: true})
			.retain(2, {color: 'red'})
			.delete(1)
		const base = new Delta()
			.insert('123', {bold: true})
			.insert('456', {italic: true})
			.insert('789', {color: 'red', bold: true})
		const expected = new Delta()
			.retain(2)
			.insert('3', {bold: true})
			.insert('4', {italic: true})
			.delete(2)
			.retain(2, {italic: true, bold: null})
			.retain(2)
			.insert('9', {color: 'red', bold: true})
		const inverted = delta.invert(base)
		expect(expected).toEqual(inverted)
		expect(base.compose(delta).compose(inverted)).toEqual(base)
	})

	describe('custom embed handler', () => {
		beforeEach(() => {
			Delta.registerEmbed<Op[]>('delta', {
				compose: (a, b) => new Delta(a).compose(new Delta(b)).ops,
				transform: (a, b, priority) => new Delta(a).transform(new Delta(b), priority).ops,
				invert: (a, b) => new Delta(a).invert(new Delta(b)).ops,
			})
		})

		afterEach(() => {
			Delta.unregisterEmbed('delta')
		})

		it('invert a normal change', () => {
			const delta = new Delta().retain(1, {bold: true})
			const base = new Delta().insert({delta: [{insert: 'a'}]})

			const expected = new Delta().retain(1, {bold: null})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('invert an embed change', () => {
			const delta = new Delta().retain({delta: [{insert: 'b'}]})
			const base = new Delta().insert({delta: [{insert: 'a'}]})

			const expected = new Delta().retain({
				delta: [{delete: 1}],
			})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('invert an embed change with numbers', () => {
			const delta = new Delta()
				.retain(1)
				.retain(1, {bold: true})
				.retain({delta: [{insert: 'b'}]})
			const base = new Delta().insert('\n\n').insert({delta: [{insert: 'a'}]})

			const expected = new Delta()
				.retain(1)
				.retain(1, {bold: null})
				.retain({
					delta: [{delete: 1}],
				})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('respects base attributes', () => {
			const delta = new Delta()
				.delete(1)
				.retain(1, {header: 2})
				.retain({delta: [{insert: 'b'}]}, {padding: 10, margin: 0})
			const base = new Delta()
				.insert('\n')
				.insert('\n', {header: 1})
				.insert({delta: [{insert: 'a'}]}, {margin: 10})

			const expected = new Delta()
				.insert('\n')
				.retain(1, {header: 1})
				.retain(
					{
						delta: [{delete: 1}],
					},
					{padding: null, margin: 10}
				)
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('works with multiple embeds', () => {
			const delta = new Delta()
				.retain(1)
				.retain({delta: [{delete: 1}]})
				.retain({delta: [{delete: 1}]})

			const base = new Delta()
				.insert('\n')
				.insert({delta: [{insert: 'a'}]})
				.insert({delta: [{insert: 'b'}]})

			const expected = new Delta()
				.retain(1)
				.retain({delta: [{insert: 'a'}]})
				.retain({delta: [{insert: 'b'}]})

			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('invert a string', () => {
			const delta = new Delta().retain({delta: [{insert: 'a'}]})
			const base = new Delta().insert('a')

			expect(() => delta.invert(base)).toThrow(new Error('cannot retain a string'))
		})
	})

	describe('nested attributes', () => {
		it('inverts adding a nested attribute', () => {
			const delta = new Delta().retain(1, {comment: {'1': true}})
			const base = new Delta().insert('A')
			const expected = new Delta().retain(1, {comment: null})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts adding a multiple nested attributes', () => {
			const delta = new Delta().retain(1, {comment: {'1': true, '2': true}})
			const base = new Delta().insert('A')
			const expected = new Delta().retain(1, {comment: null})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts adding a nested attribute to an existing map', () => {
			const delta = new Delta().retain(1, {comment: {'2': true}})
			const base = new Delta().insert('A', {
				comment: {'1': true, '99': true},
			})
			const expected = new Delta().retain(1, {comment: {'2': null}})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts removing a nested attribute', () => {
			const delta = new Delta().retain(1, {comment: null})
			const base = new Delta().insert('A', {comment: {'1': true}})
			const expected = new Delta().retain(1, {comment: {'1': true}})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})
		it('inverts removing a nested attribute from an existing map', () => {
			const delta = new Delta().retain(1, {comment: {'1': null}})
			const base = new Delta().insert('A', {
				comment: {'1': true, '2': true},
			})
			const expected = new Delta().retain(1, {comment: {'1': true}})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts a nested attribute change that split an insert', () => {
			const delta = new Delta().retain(1, {comment: {'2': true}})
			const base = new Delta().insert('AB', {
				comment: {'1': true, '99': true},
			})
			const expected = new Delta().retain(1, {comment: {'2': null}})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts removing a nested attribute that would remove the outer map', () => {
			const delta = new Delta().retain(1, {comment: {'1': null}})
			const base = new Delta().insert('A', {comment: {'1': true}})
			const expected = new Delta().retain(1, {comment: {'1': true}})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts removing a nested attribute change that joined inserts', () => {
			const delta = new Delta().retain(1).retain(1, {comment: {'2': null}})
			const base = new Delta().insert('A', {comment: {'1': true}}).insert('B', {comment: {'1': true, '2': true}})
			const expected = new Delta().retain(1).retain(1, {comment: {'2': true}})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts changing a nested value', () => {
			const delta = new Delta().retain(1, {comment: {'1': 'b'}})
			const base = new Delta().insert('A', {
				comment: {'1': 'a', '99': 'c'},
			})
			const expected = new Delta().retain(1, {comment: {'1': 'a'}})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts adding and removing nested keys in the same map', () => {
			const delta = new Delta().retain(1, {
				comment: {'1': null, '2': true},
			})
			const base = new Delta().insert('A', {
				comment: {'1': true, '99': true},
			})
			const expected = new Delta().retain(1, {
				comment: {'1': true, '2': null},
			})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts a no-op nested change', () => {
			const delta = new Delta().retain(1, {comment: {'1': true}})
			const base = new Delta().insert('A', {comment: {'1': true, '99': true}})
			const expected = new Delta()
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts a deeply nested map change', () => {
			const delta = new Delta().retain(1, {
				comment: {'1': {resolved: true}},
			})
			const base = new Delta().insert('A', {
				comment: {'1': {resolved: false, author: 'x'}, '99': true},
			})
			const expected = new Delta().retain(1, {
				comment: {'1': {resolved: false}},
			})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts changes across multiple independent map attributes', () => {
			const delta = new Delta().retain(1, {
				comment: {'2': true},
				highlight: {a: null},
			})
			const base = new Delta().insert('A', {
				comment: {'1': true, '5': true},
				highlight: {a: true, b: true},
				bold: true,
			})
			const expected = new Delta().retain(1, {
				comment: {'2': null},
				highlight: {a: true},
			})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})

		it('inverts a nested change spanning inserts where one lacks the map', () => {
			const delta = new Delta().retain(2, {comment: {'2': true}})
			const base = new Delta().insert('A', {comment: {'1': true, '99': true}}).insert('B')
			const expected = new Delta().retain(1, {comment: {'2': null}}).retain(1, {comment: null})
			const inverted = delta.invert(base)
			expect(expected).toEqual(inverted)
			expect(base.compose(delta).compose(inverted)).toEqual(base)
		})
	})
})
