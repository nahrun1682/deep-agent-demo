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
  echo '{"continue":true,"systemMessage":"skip mypy: uv not found"}'
  exit 0
fi

if ! uv run mypy --version >/dev/null 2>&1; then
  echo '{"continue":true,"systemMessage":"skip mypy: not available in uv environment"}'
  exit 0
fi

set +e
# shellcheck disable=SC2086
out="$(uv run mypy $changed 2>&1)"
code=$?
set -e

if [ $code -ne 0 ]; then
  esc_out="$(printf '%s' "$out" | jq -Rs .)"
  printf '{"continue":true,"systemMessage":"MyPy issues found:\n%s"}\n' "$(printf '%s' "$esc_out" | sed 's/^"//; s/"$//')"
  exit 0
fi

echo '{"continue":true}'
