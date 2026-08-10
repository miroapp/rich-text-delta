// eslint-disable
import cloneDeep from 'lodash.clonedeep';
import isEqual from 'lodash.isequal';

export interface AttributeMap {
  [key: string]: unknown;
}

/** `JSON.parse` produces these as *own* keys, so `Object.keys` alone does not filter them out. */
const DANGEROUS_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

function safeKeys(obj: AttributeMap): string[] {
  return Object.keys(obj).filter((key) => !DANGEROUS_KEYS.has(key));
}

/**
 * Bound on nested attribute recursion, past which input is rejected rather than
 * merged, so adversarially deep attribute maps cannot exhaust the call stack.
 */
export const MAX_NESTING_DEPTH = 20;

/**
 * Thrown instead of silently truncating a merge, which would make replicas
 * converge on different documents.
 */
export class NestingDepthExceededError extends Error {
  constructor() {
    super(`AttributeMap nesting exceeds the maximum depth of ${MAX_NESTING_DEPTH}`);
    this.name = 'NestingDepthExceededError';
  }
}

function assertWithinDepth(depth: number): void {
  if (depth >= MAX_NESTING_DEPTH) {
    throw new NestingDepthExceededError();
  }
}

/** Recursion is limited to plain objects so a custom prototype chain can never be traversed. */
function isNestedMap(value: unknown): value is AttributeMap {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return false;
  }
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

/**
 * Deep copy that strips dangerous keys at every level, so a composed result can
 * never carry one into a downstream consumer that merges it naively.
 */
/**
 * Depth-bounded stand-in for lodash isEqual, which would otherwise recurse
 * without limit and overflow the stack on deeply nested attribute values.
 */
function safeIsEqual(a: unknown, b: unknown, depth: number): boolean {
  if (a === b) {
    return true;
  }
  assertWithinDepth(depth);
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) {
      return false;
    }
    return a.every((item, index) => safeIsEqual(item, b[index], depth + 1));
  }
  if (isNestedMap(a) && isNestedMap(b)) {
    const aKeys = safeKeys(a);
    if (aKeys.length !== safeKeys(b).length) {
      return false;
    }
    return aKeys.every(
      (key) =>
        Object.prototype.hasOwnProperty.call(b, key) && safeIsEqual(a[key], b[key], depth + 1),
    );
  }
  return isEqual(a, b);
}

function safeCloneDeep(value: unknown, depth: number): unknown {
  assertWithinDepth(depth);
  if (Array.isArray(value)) {
    return value.map((item) => safeCloneDeep(item, depth + 1));
  }
  if (isNestedMap(value)) {
    return safeKeys(value).reduce<AttributeMap>((copy, key) => {
      copy[key] = safeCloneDeep(value[key], depth + 1);
      return copy;
    }, {});
  }
  return cloneDeep(value);
}

export namespace AttributeMap {
  export function compose(
    a: AttributeMap = {},
    b: AttributeMap = {},
    keepNull = false,
    depth = 0,
  ): AttributeMap | undefined {
    assertWithinDepth(depth);
    if (typeof a !== 'object') {
      a = {};
    }
    if (typeof b !== 'object') {
      b = {};
    }
    const attributes = safeKeys(b).reduce<AttributeMap>((copy, key) => {
      if (keepNull || b[key] != null) {
        copy[key] = safeCloneDeep(b[key], depth);
      }
      return copy;
    }, {});
    // `for...in` would also walk `a`'s prototype chain.
    for (const key of safeKeys(a)) {
      if (isNestedMap(a[key]) && isNestedMap(b[key])) {
        const nestedComposed = AttributeMap.compose(
          a[key] as AttributeMap,
          b[key] as AttributeMap,
          keepNull,
          depth + 1,
        );
        if (nestedComposed === undefined) {
          delete attributes[key];
        } else {
          attributes[key] = nestedComposed;
        }
      } else if (a[key] !== undefined && b[key] === undefined) {
        attributes[key] = a[key];
      }
    }
    return Object.keys(attributes).length > 0 ? attributes : undefined;
  }

  export function diff(
    a: AttributeMap = {},
    b: AttributeMap = {},
    depth = 0,
  ): AttributeMap | undefined {
    assertWithinDepth(depth);
    if (typeof a !== 'object') {
      a = {};
    }
    if (typeof b !== 'object') {
      b = {};
    }
    const attributes = safeKeys(a)
      .concat(safeKeys(b))
      .reduce<AttributeMap>((attrs, key) => {
        if (!safeIsEqual(a[key], b[key], depth + 1)) {
          if (isNestedMap(a[key]) && isNestedMap(b[key])) {
            const nestedDiff = AttributeMap.diff(
              a[key] as AttributeMap,
              b[key] as AttributeMap,
              depth + 1,
            );
            if (nestedDiff !== undefined) {
              attrs[key] = nestedDiff;
            }
          } else {
            attrs[key] = b[key] === undefined ? null : b[key];
          }
        }
        return attrs;
      }, {});
    return Object.keys(attributes).length > 0 ? attributes : undefined;
  }

  export function invert(
    attr: AttributeMap = {},
    base: AttributeMap = {},
    depth = 0,
  ): AttributeMap {
    assertWithinDepth(depth);
    attr = attr || {};
    const baseInverted = safeKeys(base).reduce<AttributeMap>((memo, key) => {
      if (!safeIsEqual(base[key], attr[key], depth + 1) && attr[key] !== undefined) {
        if (isNestedMap(base[key]) && isNestedMap(attr[key])) {
          const nested = AttributeMap.invert(
            attr[key] as AttributeMap,
            base[key] as AttributeMap,
            depth + 1,
          );
          if (Object.keys(nested).length > 0) {
            memo[key] = nested;
          }
        } else {
          memo[key] = base[key];
        }
      }
      return memo;
    }, {});
    return safeKeys(attr).reduce<AttributeMap>((memo, key) => {
      if (!safeIsEqual(attr[key], base[key], depth + 1) && base[key] === undefined) {
        memo[key] = null;
      }
      return memo;
    }, baseInverted);
  }

  export function transform(
    a: AttributeMap | undefined,
    b: AttributeMap | undefined,
    priority = false,
    depth = 0,
  ): AttributeMap | undefined {
    assertWithinDepth(depth);
    if (typeof a !== 'object') {
      return b;
    }
    if (typeof b !== 'object') {
      return undefined;
    }
    if (!priority) {
      return b; // b is unchanged when a doesn't have priority
    }
    const attributes = safeKeys(b).reduce<AttributeMap>((attrs, key) => {
      if (isNestedMap(a[key]) && isNestedMap(b[key])) {
        const attr = AttributeMap.transform(
          a[key] as AttributeMap,
          b[key] as AttributeMap,
          priority,
          depth + 1,
        );
        if (attr !== undefined) {
          attrs[key] = attr;
        }
      } else if (a[key] === undefined) {
        attrs[key] = b[key]; // null is a valid value
      }
      return attrs;
    }, {});
    return Object.keys(attributes).length > 0 ? attributes : undefined;
  }
}
