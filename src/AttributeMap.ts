// eslint-disable
import cloneDeep from 'lodash.clonedeep';
import isEqual from 'lodash.isequal';

export interface AttributeMap {
  [key: string]: unknown;
}

/** Recursion is limited to plain objects so a custom prototype chain can never be traversed. */
function isNestedMap(value: unknown): value is AttributeMap {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return false;
  }
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

export namespace AttributeMap {
  export function compose(
    a: AttributeMap = {},
    b: AttributeMap = {},
    keepNull = false,
  ): AttributeMap | undefined {
    if (typeof a !== 'object') {
      a = {};
    }
    if (typeof b !== 'object') {
      b = {};
    }
    let attributes = cloneDeep(b);
    if (!keepNull) {
      attributes = Object.keys(b).reduce<AttributeMap>((copy, key) => {
        if (attributes[key] != null) {
          copy[key] = attributes[key];
        }
        return copy;
      }, {});
    }
    // `for...in` would also walk `a`'s prototype chain.
    for (const key of Object.keys(a)) {
      if (isNestedMap(a[key]) && isNestedMap(b[key])) {
        const nestedComposed = AttributeMap.compose(
          a[key] as AttributeMap,
          b[key] as AttributeMap,
          keepNull,
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

  export function diff(a: AttributeMap = {}, b: AttributeMap = {}): AttributeMap | undefined {
    if (typeof a !== 'object') {
      a = {};
    }
    if (typeof b !== 'object') {
      b = {};
    }
    const attributes = Object.keys(a)
      .concat(Object.keys(b))
      .reduce<AttributeMap>((attrs, key) => {
        if (!isEqual(a[key], b[key])) {
          if (isNestedMap(a[key]) && isNestedMap(b[key])) {
            const nestedDiff = AttributeMap.diff(a[key] as AttributeMap, b[key] as AttributeMap);
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

  export function invert(attr: AttributeMap = {}, base: AttributeMap = {}): AttributeMap {
    attr = attr || {};
    const baseInverted = Object.keys(base).reduce<AttributeMap>((memo, key) => {
      if (!isEqual(base[key], attr[key]) && attr[key] !== undefined) {
        if (isNestedMap(base[key]) && isNestedMap(attr[key])) {
          const nested = AttributeMap.invert(attr[key] as AttributeMap, base[key] as AttributeMap);
          if (Object.keys(nested).length > 0) {
            memo[key] = nested;
          }
        } else {
          memo[key] = base[key];
        }
      }
      return memo;
    }, {});
    return Object.keys(attr).reduce<AttributeMap>((memo, key) => {
      if (!isEqual(attr[key], base[key]) && base[key] === undefined) {
        memo[key] = null;
      }
      return memo;
    }, baseInverted);
  }

  export function transform(
    a: AttributeMap | undefined,
    b: AttributeMap | undefined,
    priority = false,
  ): AttributeMap | undefined {
    if (typeof a !== 'object') {
      return b;
    }
    if (typeof b !== 'object') {
      return undefined;
    }
    if (!priority) {
      return b; // b is unchanged when a doesn't have priority
    }
    const attributes = Object.keys(b).reduce<AttributeMap>((attrs, key) => {
      if (isNestedMap(a[key]) && isNestedMap(b[key])) {
        const attr = AttributeMap.transform(
          a[key] as AttributeMap,
          b[key] as AttributeMap,
          priority,
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
