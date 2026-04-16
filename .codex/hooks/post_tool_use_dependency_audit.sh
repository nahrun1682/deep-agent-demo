#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")"
cwd="$(printf '%s' "$payload" | jq -r '.cwd // ""' 2>/dev/null || pwd)"

if ! printf '%s' "$cmd" | grep -q 'pyproject.toml'; then
  exit 0
fi

audit_tool=""
if command -v uv >/dev/null 2>&1 && command -v uvx >/dev/null 2>&1; then
  audit_tool="uvx pip-audit"
elif command -v safety >/dev/null 2>&1; then
  audit_tool="safety"
elif command -v pip-audit >/dev/null 2>&1; then
  audit_tool="pip-audit"
fi

if [ -z "$audit_tool" ]; then
  echo '{"systemMessage":"Dependency audit skipped: no audit tool found (uv/safety/pip-audit)."}'
  exit 0
fi

set +e
if [ "$audit_tool" = "uvx pip-audit" ]; then
  out="$(uvx pip-audit --path "$cwd" 2>&1)"
  code=$?
elif [ "$audit_tool" = "safety" ]; then
  out="$(safety check 2>&1)"
  code=$?
else
  out="$(pip-audit 2>&1)"
  code=$?
fi
set -e

if [ $code -ne 0 ]; then
  esc_out="$(printf '%s' "$out" | jq -Rs .)"
  printf '{"systemMessage":"Dependency audit (%s) reported issues.\\n%s"}\n' "$audit_tool" "$(printf '%s' "$esc_out" | sed 's/^"//; s/"$//')"
fi
