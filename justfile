# https://just.systems
#
# Recipes are grouped per language under `languages/`. Aggregate recipes (`test`,
# `lint`, `ci`, ...) fan out to every language; the `-ts` suffixed recipes target
# the TypeScript package only. New languages get their own suffix and are added to
# the aggregate recipe's dependency list.

# `-i` so nvm (a shell function, not a binary) is available in recipes
set shell := ["zsh", "-i", "-c"]

ts_dir := "languages/typescript"
py_dir := "languages/python"

# `nvm use` picks up languages/typescript/.nvmrc
npm := "cd " + ts_dir + " && nvm use --silent && npm"

# uv reads the interpreter and dev dependencies from languages/python/pyproject.toml
uv := "cd " + py_dir + " && uv"

# list available recipes
default:
    @just --list --unsorted

# install dependencies for every language
install: install-ts install-py

# lint every language
lint: lint-ts lint-py

# fix auto-fixable lint violations in every language
lint-fix: lint-fix-ts lint-fix-py

# format every language in place
format: format-ts format-py

# check formatting for every language without writing
format-check: format-check-ts format-check-py

# typecheck every language
typecheck: typecheck-ts typecheck-py

# run the test suite for every language
test: test-ts test-py

# build every language's distributable artifacts
build: build-ts build-py

# run the full check suite for every language, as CI does
ci: ci-ts ci-py

# delete build output and installed dependencies for every language
clean: clean-ts clean-py

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

# ---------------------------------------------------------------------------
# Python (languages/python)
# ---------------------------------------------------------------------------

# install Python dependencies into languages/python/.venv from the lockfile
install-py:
    {{ uv }} sync

# install Python dependencies exactly as locked, failing if the lockfile is stale
install-py-ci:
    {{ uv }} sync --locked

# lint the Python package with ruff
lint-py: install-py
    {{ uv }} run ruff check .

# apply ruff's auto-fixes to the Python package
lint-fix-py: install-py
    {{ uv }} run ruff check . --fix

# format the Python package in place with ruff
format-py: install-py
    {{ uv }} run ruff format .

# check Python formatting without writing
format-check-py: install-py
    {{ uv }} run ruff format --check .

# typecheck the Python package with mypy
typecheck-py: install-py
    {{ uv }} run mypy

# run the Python tests once; extra args go to pytest (e.g. `just test-py -k transform`)
test-py *args: install-py
    {{ uv }} run pytest {{ args }}

# build the Python sdist and wheel into languages/python/dist/
build-py: install-py
    {{ uv }} build

# run lint, format-check, typecheck, test and build for the Python package
ci-py: lint-py format-check-py typecheck-py test-py build-py

# delete the Python package's dist/, .venv/ and caches
clean-py:
    rm -rf {{ py_dir }}/dist {{ py_dir }}/.venv {{ py_dir }}/.pytest_cache {{ py_dir }}/.mypy_cache {{ py_dir }}/.ruff_cache
    find {{ py_dir }} -name __pycache__ -type d -prune -exec rm -rf {} +

# print the version in the Python pyproject.toml
version-py:
    @{{ uv }} version --short

# set the Python package version (e.g. `just set-version-py 0.2.0`)
set-version-py version:
    {{ uv }} version {{ version }}
