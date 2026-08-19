import { readFileSync } from 'node:fs';
import path, { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'yaml';
import { afterEach, describe, expect, it } from 'vitest';
import type { EmbedHandler } from '../Delta';
import { Delta } from '../Delta';
import { AttributeMap } from '../AttributeMap';
import { Op } from '../Op';
import { glob } from 'node:fs/promises';

const CORPUS_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'declarative-test-corpus');

// --- corpus format -------------------------------------------------------

type ParamType = 'delta' | 'attrs' | 'op' | 'bool' | 'int' | 'calls';

interface Param {
  name: string;
  type: ParamType;
}

interface MethodSpec {
  /**
   * Every argument the method takes, receiver included. Positional order is this
   * port's calling convention; only the names are part of the corpus.
   */
  params: Param[];
  invoke: (args: unknown[]) => unknown;
}

/** JSON-encoded values in the YAML, decoded before dispatch. */
const JSON_TYPES: ReadonlySet<ParamType> = new Set<ParamType>(['delta', 'attrs', 'op']);

/** An instance method's receiver is an ordinary argument named `receiver`. */
const RECEIVER: Param = { name: 'receiver', type: 'delta' };

/**
 * Types with no meaningful absent value, so leaving one out — whether by omitting
 * the key or writing `null` — is an authoring error rather than a case. `bool`
 * and `int` arguments all have defaults, and an absent `attrs` argument is itself
 * under test.
 */
const REQUIRED_TYPES: ReadonlySet<ParamType> = new Set<ParamType>(['delta', 'op', 'calls']);

const METHODS: Record<string, MethodSpec> = {
  'Delta.compose': {
    params: [RECEIVER, { name: 'other', type: 'delta' }],
    invoke: ([receiver, other]) => (receiver as Delta).compose(other as Delta).ops,
  },
  'Delta.transform': {
    params: [RECEIVER, { name: 'other', type: 'delta' }, { name: 'priority', type: 'bool' }],
    invoke: ([receiver, other, priority]) =>
      (receiver as Delta).transform(other as Delta, priority as boolean | undefined).ops,
  },
  'Delta.transformPosition': {
    params: [RECEIVER, { name: 'index', type: 'int' }, { name: 'priority', type: 'bool' }],
    invoke: ([receiver, index, priority]) =>
      (receiver as Delta).transformPosition(index as number, priority as boolean | undefined),
  },
  'Delta.invert': {
    params: [RECEIVER, { name: 'base', type: 'delta' }],
    invoke: ([receiver, base]) => (receiver as Delta).invert(base as Delta).ops,
  },
  'Delta.diff': {
    params: [RECEIVER, { name: 'other', type: 'delta' }],
    invoke: ([receiver, other]) => (receiver as Delta).diff(other as Delta).ops,
  },
  'Delta.concat': {
    params: [RECEIVER, { name: 'other', type: 'delta' }],
    invoke: ([receiver, other]) => (receiver as Delta).concat(other as Delta).ops,
  },
  'Delta.chop': {
    params: [RECEIVER],
    invoke: ([receiver]) => (receiver as Delta).chop().ops,
  },
  'Delta.slice': {
    params: [RECEIVER, { name: 'start', type: 'int' }, { name: 'end', type: 'int' }],
    invoke: ([receiver, start, end]) =>
      (receiver as Delta).slice(start as number | undefined, end as number | undefined).ops,
  },
  'Delta.length': {
    params: [RECEIVER],
    invoke: ([receiver]) => (receiver as Delta).length(),
  },
  'Delta.build': {
    params: [{ name: 'calls', type: 'calls' }],
    invoke: ([calls]) => build(calls as BuilderCall[]).ops,
  },
  'AttributeMap.compose': {
    params: [
      { name: 'a', type: 'attrs' },
      { name: 'b', type: 'attrs' },
      { name: 'keepNull', type: 'bool' },
      { name: 'depth', type: 'int' },
    ],
    invoke: ([a, b, keepNull, depth]) =>
      AttributeMap.compose(
        a as AttributeMap | undefined,
        b as AttributeMap | undefined,
        keepNull as boolean | undefined,
        depth as number | undefined,
      ),
  },
  'AttributeMap.diff': {
    params: [
      { name: 'a', type: 'attrs' },
      { name: 'b', type: 'attrs' },
      { name: 'depth', type: 'int' },
    ],
    invoke: ([a, b, depth]) =>
      AttributeMap.diff(
        a as AttributeMap | undefined,
        b as AttributeMap | undefined,
        depth as number | undefined,
      ),
  },
  'AttributeMap.invert': {
    params: [
      { name: 'attr', type: 'attrs' },
      { name: 'base', type: 'attrs' },
      { name: 'depth', type: 'int' },
    ],
    invoke: ([attr, base, depth]) =>
      AttributeMap.invert(
        attr as AttributeMap | undefined,
        base as AttributeMap | undefined,
        depth as number | undefined,
      ),
  },
  'AttributeMap.transform': {
    params: [
      { name: 'a', type: 'attrs' },
      { name: 'b', type: 'attrs' },
      { name: 'priority', type: 'bool' },
      { name: 'depth', type: 'int' },
    ],
    invoke: ([a, b, priority, depth]) =>
      AttributeMap.transform(
        a as AttributeMap | undefined,
        b as AttributeMap | undefined,
        priority as boolean | undefined,
        depth as number | undefined,
      ),
  },
  'Op.length': {
    params: [{ name: 'op', type: 'op' }],
    invoke: ([op]) => Op.length(op as Op),
  },
};

/** Named embed handlers a case may request via `embeds`. */
const EMBED_HANDLERS: Record<string, EmbedHandler<Op[]>> = {
  // An embed whose value is an ops array, composed/transformed/inverted by
  // recursing into Delta itself. Self-referential, so every port can implement
  // it without any user-supplied logic.
  'nested-delta': {
    compose: (a, b) => new Delta(a).compose(new Delta(b)).ops,
    transform: (a, b, priority) => new Delta(a).transform(new Delta(b), priority).ops,
    invert: (a, b) => new Delta(a).invert(new Delta(b)).ops,
  },
};

/** Maps this implementation's error messages onto the corpus error kinds. */
const ERROR_KINDS: ReadonlyArray<readonly [RegExp, string]> = [
  [/^cannot retain a /, 'cannot-retain-non-embed'],
  [/^embed types not matched: /, 'embed-types-mismatch'],
  [/^no handlers for embed type /, 'no-embed-handler'],
  [/^diff\(\) called (on|with) non-document$/, 'diff-non-document'],
];

const INVARIANTS = ['composes-to-other'] as const;

interface BuilderCall {
  op: 'insert' | 'delete' | 'retain' | 'push';
  args?: Record<string, unknown>;
}

interface TestCase {
  name: string;
  method: string;
  args?: Record<string, unknown>;
  embeds?: Record<string, string>;
  expected?: string | null;
  error?: { kind: string };
  invariant?: string;
  maxInserted?: number;
  maxDeleted?: number;
}

// --- loading -------------------------------------------------------------

async function listYamlFiles(): Promise<string[]> {
  const out: string[] = [];
  for await (const entry of glob(`${CORPUS_ROOT}/**/*.{yaml,yml}`)) {
    out.push(entry);
  }
  return out.sort();
}

const onDisk = await listYamlFiles();

// --- dispatch ------------------------------------------------------------

function build(calls: BuilderCall[]): Delta {
  const delta = new Delta();
  for (const call of calls) {
    const args = call.args ?? {};
    const has = (k: string) => Object.prototype.hasOwnProperty.call(args, k);
    const attrs = has('attributes')
      ? (JSON.parse(args.attributes as string) as AttributeMap | null)
      : undefined;
    switch (call.op) {
      case 'insert':
        delta.insert(JSON.parse(args.arg as string), attrs);
        break;
      case 'retain':
        delta.retain(JSON.parse(args.arg as string), attrs);
        break;
      case 'delete':
        delta.delete(args.length as number);
        break;
      case 'push':
        delta.push(JSON.parse(args.op as string) as Op);
        break;
      default:
        throw new Error(`unknown builder op: ${String(call.op)}`);
    }
  }
  return delta;
}

function decode(type: ParamType, raw: unknown): unknown {
  if (!JSON_TYPES.has(type)) {
    return raw;
  }
  const value = JSON.parse(raw as string);
  return type === 'delta' ? new Delta(value as Op[]) : value;
}

/**
 * Whether the case supplies an argument. A `null` counts as not supplied and is
 * passed as `undefined`, which is how the reference treats an argument left out:
 * every optional parameter has a default. `attributes.yaml` spells out every
 * argument and writes `null` for the ones it does not supply, rather than
 * omitting the key; both spellings mean the same thing here. Unrelated to a
 * `null` *inside* a JSON value, which is an attribute removal.
 */
function suppliedArg(testCase: TestCase, name: string): boolean {
  const args = testCase.args ?? {};
  return Object.prototype.hasOwnProperty.call(args, name) && args[name] !== null;
}

function positionalArgs(spec: MethodSpec, testCase: TestCase): unknown[] {
  return spec.params.map((param) =>
    suppliedArg(testCase, param.name) ? decode(param.type, testCase.args![param.name]) : undefined,
  );
}

/**
 * Strict structural form: objects are unordered key->value maps, arrays are
 * ordered, numbers compare by value, and an absent key is NOT equal to one
 * holding an empty map. Round-tripping through JSON drops keys whose value is
 * `undefined` (not representable on the wire) while preserving `{}`.
 */
function structural(value: unknown): unknown {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function classify(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  for (const [pattern, kind] of ERROR_KINDS) {
    if (pattern.test(message)) {
      return kind;
    }
  }
  throw new Error(`unclassified error, no corpus kind matches: ${message}`);
}

function editSize(ops: Op[]): { inserted: number; deleted: number } {
  let inserted = 0;
  let deleted = 0;
  for (const op of ops) {
    if (op.insert != null) {
      inserted += typeof op.insert === 'string' ? op.insert.length : 1;
    }
    if (typeof op.delete === 'number') {
      deleted += op.delete;
    }
  }
  return { inserted, deleted };
}

// --- validation ----------------------------------------------------------

function validate(file: string, testCase: TestCase, seen: Set<string>): MethodSpec {
  const where = `${file} :: ${testCase.name}`;
  if (!testCase.name) {
    throw new Error(`${file}: a case is missing \`name\``);
  }
  if (seen.has(testCase.name)) {
    throw new Error(`${where}: duplicate case name within the file`);
  }
  seen.add(testCase.name);

  const spec = METHODS[testCase.method];
  if (!spec) {
    throw new Error(`${where}: unknown method \`${testCase.method}\``);
  }
  const allowed = new Set(spec.params.map((param) => param.name));
  for (const key of Object.keys(testCase.args ?? {})) {
    if (!allowed.has(key)) {
      throw new Error(`${where}: \`${testCase.method}\` has no argument \`${key}\``);
    }
  }
  for (const param of spec.params) {
    if (REQUIRED_TYPES.has(param.type) && !suppliedArg(testCase, param.name)) {
      throw new Error(`${where}: \`${testCase.method}\` requires argument \`${param.name}\``);
    }
  }

  const forms = [
    Object.prototype.hasOwnProperty.call(testCase, 'expected'),
    testCase.error !== undefined,
    testCase.invariant !== undefined,
  ].filter(Boolean);
  if (forms.length !== 1) {
    throw new Error(`${where}: expected exactly one of \`expected\`, \`error\`, \`invariant\``);
  }
  if (testCase.error && !ERROR_KINDS.some(([, kind]) => kind === testCase.error!.kind)) {
    throw new Error(`${where}: unknown error kind \`${testCase.error.kind}\``);
  }
  if (testCase.invariant && !INVARIANTS.includes(testCase.invariant as 'composes-to-other')) {
    throw new Error(`${where}: unknown invariant \`${testCase.invariant}\``);
  }
  for (const name of Object.keys(testCase.embeds ?? {})) {
    if (!EMBED_HANDLERS[testCase.embeds![name]]) {
      throw new Error(`${where}: unknown embed handler \`${testCase.embeds![name]}\``);
    }
  }
  return spec;
}

// --- execution -----------------------------------------------------------

function run(file: string, testCase: TestCase, spec: MethodSpec): void {
  const where = `${file} :: ${testCase.name}`;
  for (const [type, handler] of Object.entries(testCase.embeds ?? {})) {
    Delta.registerEmbed<Op[]>(type, EMBED_HANDLERS[handler]);
  }

  const args = positionalArgs(spec, testCase);

  if (testCase.error) {
    let thrown: unknown;
    try {
      spec.invoke(args);
    } catch (error) {
      thrown = error;
    }
    expect(thrown, `${where}: expected a thrown error`).toBeDefined();
    expect(classify(thrown)).toBe(testCase.error.kind);
    return;
  }

  const actual = spec.invoke(args);

  if (testCase.invariant) {
    // `diff` decomposition is algorithm-dependent, so the corpus asserts that
    // applying the result reproduces the target document, plus a ceiling on
    // edit size so a degenerate delete-all-and-reinsert cannot pass.
    const result = new Delta(actual as Op[]);
    const applied = new Delta(JSON.parse(testCase.args!.receiver as string) as Op[]).compose(
      result,
    ).ops;
    expect(structural(applied), `${where}: applying the diff must reproduce \`other\``).toEqual(
      JSON.parse(testCase.args!.other as string),
    );
    const { inserted, deleted } = editSize(result.ops);
    expect(inserted, `${where}: inserted characters`).toBeLessThanOrEqual(testCase.maxInserted!);
    expect(deleted, `${where}: deleted characters`).toBeLessThanOrEqual(testCase.maxDeleted!);
    return;
  }

  if (testCase.expected === null) {
    expect(actual, `${where}: expected no result`).toBeUndefined();
    return;
  }

  const expected = JSON.parse(testCase.expected as string);
  expect(structural(actual), where).toStrictEqual(expected);
}

for (const file of onDisk) {
  const parsed = parse(readFileSync(file, 'utf8')) as { tests?: TestCase[] };
  const cases = parsed?.tests ?? [];

  describe(path.relative(CORPUS_ROOT, file), () => {
    const seen = new Set<string>();

    afterEach(() => {
      for (const type of Object.keys(EMBED_HANDLERS)) {
        Delta.unregisterEmbed(type);
      }
      Delta.unregisterEmbed('delta');
    });

    it('is non-empty', () => {
      expect(cases.length).toBeGreaterThan(0);
    });

    for (const testCase of cases) {
      const spec = validate(file, testCase, seen);
      it(testCase.name, () => {
        run(file, testCase, spec);
      });
    }
  });
}
