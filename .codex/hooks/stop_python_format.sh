#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
cwd="$(printf '%s' "$payload" | jq -r '.cwd // ""' 2>/dev/null || pwd)"

if [ ! -f "$cwd/pyproject.toml" ]; then
  echo '{"continue":true}'
  exit 0
fi

cd "$cwd"

changed="$(git diff --name-only --diff-filter=ACMR 2>/dev/null | grep '\.py$' || true)"
if [ -z "$changed" ]; then
  echo '{"continue":true}'
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo '{"continue":true,"systemMessage":"skip format: uv not found"}'
  exit 0
fi

# shellcheck disable=SC2086
uv run ruff check --fix --quiet $changed >/dev/null 2>&1 || true
# shellcheck disable=SC2086
uv run ruff format --quiet $changed >/dev/null 2>&1 || true

echo '{"continue":true}'
