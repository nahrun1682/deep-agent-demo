#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")"
ts="$(date -Iseconds)"

log_path="$HOME/.codex/notifications.log"
mkdir -p "$(dirname "$log_path")"
printf 'Codex notification: %s command=%s\n' "$ts" "$cmd" >> "$log_path"
