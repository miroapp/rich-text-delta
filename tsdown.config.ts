import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { defineConfig } from 'tsdown';

const OUT_DIR = 'dist';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['esm', 'cjs'],
  dts: true,
  // Keep tsup's output names (index.js/.cjs, index.d.ts/.d.cts) so the paths in
  // the published "exports" map stay unchanged; tsdown defaults to .mjs/.d.mts.
  fixedExtension: false,
  sourcemap: true,
  clean: true,
  treeshake: true,
  target: 'es2015',
  outDir: OUT_DIR,
  hooks: {
    // TypeScript 7's API doesn't emit declaration maps, but tsdown still
    // appends a sourceMappingURL to the .d.ts/.d.cts when sourcemap is on.
    // Drop the dangling reference so we don't ship a pointer to a missing file.
    'build:done': async () => {
      const files = await readdir(OUT_DIR);
      await Promise.all(
        files
          .filter((file) => file.endsWith('.d.ts') || file.endsWith('.d.cts'))
          .map(async (file) => {
            const path = join(OUT_DIR, file);
            const source = await readFile(path, 'utf8');
            const stripped = source.replace(/\n?\/\/# sourceMappingURL=.*\.map\s*$/, '\n');
            if (stripped !== source) await writeFile(path, stripped);
          }),
      );
    },
  },
});
