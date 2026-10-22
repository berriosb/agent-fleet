#!/usr/bin/env bash
# Multi-profile plugin + startup audit for Hermes Agent.
#
# Usage: scripts/audit-profiles.sh [profile ...]
#   no args  -> `default` plus every directory under ~/.hermes/profiles/
#
# Uses `hermes -p <profile>`, never `HERMES_HOME=... hermes`: with
# terminal.auto_source_bashrc=true the shell init re-exports HERMES_HOME and
# silently overrides an inline assignment, so every "different" profile would
# report the same plugin list.
#
# Env: HERMES_BIN (default: hermes), HERMES_ROOT (default: ~/.hermes),
#      RUNS (timing runs per profile, default: 3)

set -uo pipefail
HERMES_BIN="${HERMES_BIN:-hermes}"
ROOT="${HERMES_ROOT:-$HOME/.hermes}"
RUNS="${RUNS:-3}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

profiles() {
  if [ "$#" -gt 0 ]; then printf '%s\n' "$@"; return; fi
  printf 'default\n'
  [ -d "$ROOT/profiles" ] && ls -1 "$ROOT/profiles" 2>/dev/null
}

home_of() {
  if [ "$1" = "default" ]; then printf '%s' "$ROOT"; else printf '%s/profiles/%s' "$ROOT" "$1"; fi
}

ms_since() { echo $(( ($(date +%s%N) - $1) / 1000000 )); }

for p in $(profiles); do
  h=$(home_of "$p")
  echo "════════ ${p} ════════"

  # Declared: strip only the leading list marker so hyphenated names survive.
  "$HERMES_BIN" -p "$p" config get plugins.enabled 2>/dev/null \
    | sed 's/^[[:space:]]*-[[:space:]]*//; s/^[[:space:]]*//; s/[]["'\'']//g; s/,$//' \
    | grep -v '^$' | sort -u > "$TMP/declared" || true

  echo "-- declared (config.yaml plugins.enabled):"
  sed 's/^/   /' "$TMP/declared"; [ -s "$TMP/declared" ] || echo "   (none)"

  echo "-- loaded (actually running at boot):"
  "$HERMES_BIN" -p "$p" plugins list --plain --no-bundled 2>/dev/null \
    | awk '$1 == "enabled" { print $NF }' | sort -u > "$TMP/loaded" || true
  sed 's/^/   /' "$TMP/loaded"; [ -s "$TMP/loaded" ] || echo "   (none)"

  echo "-- installed on disk:"
  if [ -d "$h/plugins" ]; then ls -1 "$h/plugins" 2>/dev/null | sed 's/^/   /'
  else echo "   (no plugins dir)"; fi

  # Orphan candidates only. Confirm each with `hermes plugins show <name>`
  # before acting: a bundled plugin can be enabled without an install dir.
  echo "-- orphan candidates (declared but not loaded) -- confirm with 'plugins show' first:"
  orphans=$(comm -23 "$TMP/declared" "$TMP/loaded")
  if [ -n "$orphans" ]; then printf '%s\n' "$orphans" | sed 's/^/   /'; else echo "   (none)"; fi

  if [ -f "$h/logs/errors.log" ]; then
    echo "-- errors.log signals (all-time):"
    for pat in "event loop stalled" "dictionary changed size" "Failed to load plugin" "not installed"; do
      printf '   %-24s %s\n' "$pat" "$(grep -c "$pat" "$h/logs/errors.log" 2>/dev/null || echo 0)"
    done
  else
    echo "-- errors.log: (absent)"
  fi

  # First run is a cold import; the remaining runs show the warm cost.
  echo -n "-- startup (${RUNS} runs, first is cold):"
  for _ in $(seq 1 "$RUNS"); do
    s=$(date +%s%N)
    "$HERMES_BIN" -p "$p" plugins list --plain --no-bundled >/dev/null 2>&1
    printf ' %sms' "$(ms_since "$s")"
  done
  echo
  echo
done