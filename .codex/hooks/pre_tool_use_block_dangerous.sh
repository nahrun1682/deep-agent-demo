#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")"

if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])(sudo[[:space:]]+)?rm[[:space:]]+-rf([[:space:]]|$)'; then
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Dangerous command blocked by Codex hook policy."}}
JSON
  exit 0
fi

if printf '%s' "$cmd" | grep -Eq '(^|[[:space:]])mkfs(\.|[[:space:]])'; then
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Dangerous command blocked by Codex hook policy."}}
JSON
  exit 0
fi

if printf '%s' "$cmd" | grep -Eq ':[[:space:]]*\([[:space:]]*\)[[:space:]]*\{[[:space:]]*:[|]:[[:space:]]*&[[:space:]]*\}[[:space:]]*;[[:space:]]*:'; then
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Dangerous command blocked by Codex hook policy."}}
JSON
  exit 0
fi
