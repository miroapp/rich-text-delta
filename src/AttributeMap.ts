// Copyright (c) 2022, Slab, Inc.
// Copyright (c) 2026, RealtimeBoard, Inc. dba Miro
// SPDX-License-Identifier: BSD-3-Clause

// eslint-disable
import { isEqual } from 'es-toolkit';

const MAX_RECURSION_DEPTH = 100;

export interface AttributeMap {
  [key: string]: unknown;
}

function isNestedMap(value: unknown): value is AttributeMap {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function safeKeys(map: AttributeMap): string[] {
  return Object.keys(map).filter((key) => key !== '__proto__');
}

export namespace AttributeMap {
  export function compose(
    a: AttributeMap = {},
    b: AttributeMap = {},
    keepNull = false,
    depth = MAX_RECURSION_DEPTH,
  ): AttributeMap | undefined {
    if (typeof a !== 'object') {
      a = {};
    }
    if (typeof b !== 'object') {
      b = {};
    }
    let attributes = structuredClone(b);
    if (!keepNull) {
      attributes = deepKeepNull(b, depth) ?? {};
    }
    safeKeys(a).forEach((key) => {
      if (isNestedMap(a[key]) && isNestedMap(b[key]) && depth > 1) {
        const nestedComposed = AttributeMap.compose(
          a[key] as AttributeMap,
          b[key] as AttributeMap,
          keepNull,
          depth - 1,
        );
        if (nestedComposed === undefined) {
          delete attributes[key];
        } else {
          attributes[key] = nestedComposed;
        }
      } else if (a[key] !== undefined && b[key] === undefined) {
        attributes[key] = a[key];
      }
    });
    return Object.keys(attributes).length > 0 ? attributes : undefined;
  }

  function deepKeepNull(attr: AttributeMap, depth: number): AttributeMap | undefined {
    if (depth <= 1) {
      return attr;
    }

    let attributes: AttributeMap = {};
    for (const key of safeKeys(attr)) {
      if (isNestedMap(attr[key])) {
        const res = deepKeepNull(attr[key], depth - 1);
        if (res === undefined) {
          continue;
        } else {
          attributes[key] = res;
        }
      } else if (attr[key] != null) {
        attributes[key] = attr[key];
      }
    }

    return Object.keys(attributes).length > 0 ? attributes : undefined;
  }

  export function diff(
    a: AttributeMap = {},
    b: AttributeMap = {},
    depth = MAX_RECURSION_DEPTH,
  ): AttributeMap | undefined {
    if (typeof a !== 'object') {
      a = {};
    }
    if (typeof b !== 'object') {
      b = {};
    }
    const attributes = safeKeys(structuredClone(a))
      .concat(safeKeys(structuredClone(b)))
      .reduce<AttributeMap>((attrs, key) => {
        if (!isEqual(a[key], b[key])) {
          if (isNestedMap(a[key]) && isNestedMap(b[key]) && depth > 1) {
            const nestedDiff = AttributeMap.diff(
              a[key] as AttributeMap,
              b[key] as AttributeMap,
              depth - 1,
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
    depth = MAX_RECURSION_DEPTH,
  ): AttributeMap {
    attr = attr || {};
    const baseInverted = safeKeys(base).reduce<AttributeMap>((memo, key) => {
      if (!isEqual(base[key], attr[key]) && attr[key] !== undefined) {
        if (isNestedMap(base[key]) && isNestedMap(attr[key]) && depth > 1) {
          const nested = AttributeMap.invert(
            attr[key] as AttributeMap,
            base[key] as AttributeMap,
            depth - 1,
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
    depth = MAX_RECURSION_DEPTH,
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
    const attributes = safeKeys(b).reduce<AttributeMap>((attrs, key) => {
      if (isNestedMap(a[key]) && isNestedMap(b[key]) && depth > 1) {
        const attr = AttributeMap.transform(
          a[key] as AttributeMap,
          b[key] as AttributeMap,
          priority,
          depth - 1,
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
