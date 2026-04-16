#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // ""' 2>/dev/null || echo "")"
desc="$(printf '%s' "$payload" | jq -r '.description // ""' 2>/dev/null || echo "")"
session_id="$(printf '%s' "$payload" | jq -r '.session_id // ""' 2>/dev/null || echo "")"

ts="$(date -Iseconds)"
log_path="$HOME/.codex/bash-command-log.txt"
mkdir -p "$(dirname "$log_path")"
printf '%s\tsession=%s\tcommand=%s\tdescription=%s\n' "$ts" "$session_id" "$cmd" "$desc" >> "$log_path"
