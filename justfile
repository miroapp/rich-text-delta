# https://just.systems
#
# Recipes are grouped per language under `languages/`. Aggregate recipes (`test`,
# `lint`, `ci`, ...) fan out to every language; the `-ts` suffixed recipes target
# the TypeScript package only. New languages get their own suffix and are added to
# the aggregate recipe's dependency list.

# `-i` so nvm (a shell function, not a binary) is available in recipes
set shell := ["zsh", "-i", "-c"]

ts_dir := "languages/typescript"

# `nvm use` picks up languages/typescript/.nvmrc
npm := "cd " + ts_dir + " && nvm use --silent && npm"

# list available recipes
default:
    @just --list --unsorted

# install dependencies for every language
install: install-ts

# lint every language
lint: lint-ts

# fix auto-fixable lint violations in every language
lint-fix: lint-fix-ts

# format every language in place
format: format-ts

# check formatting for every language without writing
format-check: format-check-ts

# typecheck every language
typecheck: typecheck-ts

# run the test suite for every language
test: test-ts

# build every language's distributable artifacts
build: build-ts

# run the full check suite for every language, as CI does
ci: ci-ts

# delete build output and installed dependencies for every language
clean: clean-ts

# ---------------------------------------------------------------------------
# TypeScript (languages/typescript)
# ---------------------------------------------------------------------------

# install TypeScript dependencies from the lockfile
install-ts:
    {{ npm }} install

# install TypeScript dependencies exactly as locked (CI-style, deletes node_modules)
install-ts-ci:
    {{ npm }} ci

# lint the TypeScript package with oxlint
lint-ts: install-ts
    {{ npm }} run lint

# apply oxlint's auto-fixes to the TypeScript package
lint-fix-ts: install-ts
    {{ npm }} run lint:fix

# format the TypeScript package in place with oxfmt
format-ts: install-ts
    {{ npm }} run format

# check TypeScript formatting without writing
format-check-ts: install-ts
    {{ npm }} run format:check

# typecheck the TypeScript package with tsc
typecheck-ts: install-ts
    {{ npm }} run typecheck

# run the TypeScript tests once; extra args go to vitest (e.g. `just test-ts transform`)
test-ts *args: install-ts
    {{ npm }} run test -- {{ args }}

# run the TypeScript tests in watch mode
test-watch-ts *args: install-ts
    {{ npm }} run test:watch -- {{ args }}

# bundle the TypeScript package to dist/
build-ts: install-ts
    {{ npm }} run build

# rebuild the TypeScript package on change
dev-ts: install-ts
    {{ npm }} run dev

# run lint, format:check, typecheck, test and build for the TypeScript package
ci-ts: install-ts
    {{ npm }} run ci

# delete the TypeScript package's dist/, node_modules/ and caches
clean-ts:
    rm -rf {{ ts_dir }}/dist {{ ts_dir }}/node_modules {{ ts_dir }}/coverage {{ ts_dir }}/*.tsbuildinfo

# print the version in the TypeScript package.json
version-ts:
    @node -p "require('./{{ ts_dir }}/package.json').version"

# set the TypeScript package version without tagging or committing (e.g. `just set-version-ts 0.2.0`)
set-version-ts version:
    {{ npm }} version {{ version }} --no-git-tag-version

# pack the TypeScript package into a tarball to inspect what npm would publish
pack-ts: install-ts
    {{ npm }} pack --dry-run
