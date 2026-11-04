#!/usr/bin/env bash
# Riverview Controlled Source
# File: scripts/operations/invoke-riverview-ssh.sh
# Component: OPERATIONS-SSH-WRAPPER
# File Revision: 1.0.0
# Created: 2026-11-01 UTC (exact time unverified)
# Created By: ChatGPT GPT-6
# Purpose: Run a literal Bash file through an existing SSH alias.
# Execution Model: One remote Bash invocation.
# Observability: stdout, stderr, exit code, optional clipboard.
# Dependencies: bash, ssh, sed, mktemp, tee; optional clipboard utility.
# Authority: Steward instruction; no host configuration changes.
# Changed: 2026-11-01 UTC | SSH-WRAPPER-001 | Initial implementation
# Supersedes: None
# Contracts: R3 hints/deployment.md; R2 machine-access index is read-only reference
# Tests: Pending Linux execution
# History/Predecessor: Adapted from read-only R2 reference branch engineering/canonical-shell-wrappers-20261101
set -uo pipefail
clear 2>/dev/null || true
if [[ $# -lt 2 || $# -gt 3 ]]; then
  printf 'Usage: %s SSH_ALIAS SCRIPT_FILE [--clipboard]\n' "$0" >&2
  exit 2
fi
alias_name=$1
script_file=$2
clipboard=${3:-}
if [[ ! -f "$script_file" ]]; then
  printf 'Script not found: %s\n' "$script_file" >&2
  exit 2
fi
if [[ -n "$clipboard" && "$clipboard" != '--clipboard' ]]; then
  printf 'Unknown option: %s\n' "$clipboard" >&2
  exit 2
fi
tmp=$(mktemp) || exit 2
result=$(mktemp) || { rm -f "$tmp"; exit 2; }
trap 'rm -f "$tmp" "$result"' EXIT
sed 's/\r$//' "$script_file" > "$tmp"
if [[ -s "$tmp" && "$(tail -c 1 "$tmp" | od -An -tu1 | tr -d '[:space:]')" != 10 ]]; then
  printf '\n' >> "$tmp"
fi
printf 'TARGET_ALIAS=%s\n' "$alias_name" | tee "$result"
ssh -o BatchMode=yes -o ConnectTimeout=8 "$alias_name" bash -s < "$tmp" 2>&1 | tee -a "$result"
rc=${PIPESTATUS[0]}
printf 'SSH_EXIT_CODE=%s\n' "$rc" | tee -a "$result"
if [[ "$clipboard" == '--clipboard' ]]; then
  if command -v wl-copy >/dev/null 2>&1; then wl-copy < "$result"
  elif command -v xclip >/dev/null 2>&1; then xclip -selection clipboard < "$result"
  elif command -v xsel >/dev/null 2>&1; then xsel --clipboard --input < "$result"
  elif command -v pbcopy >/dev/null 2>&1; then pbcopy < "$result"
  else printf 'Clipboard utility unavailable; stdout retained.\n' >&2
  fi
fi
exit "$rc"
