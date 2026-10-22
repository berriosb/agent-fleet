#!/usr/bin/env bash
# Read-only mechanical sweep of a Hermes profile. Reports candidates; decides nothing.
# Usage: profile_audit.sh [profile-name]   (default: the active profile)
set -uo pipefail

PROFILE="${1:-${HERMES_PROFILE:-codehak}}"
H="$HOME/.hermes/profiles/$PROFILE"
ROOT="$HOME/.hermes"
sec() { printf '\n=== %s ===\n' "$1"; }

[ -d "$H" ] || { echo "no such profile: $H"; exit 1; }

sec "VERSION (pin before judging any key)"
hermes --version 2>&1 | head -3

sec "CONFIG: version, deprecations, inert features"
hermes doctor 2>&1 | grep -iE 'config version|deprecat|no longer applied|not logged in|issue\(s\)|⚠' | head -30

sec "GATEWAY WARNINGS: keys accepted but ignored"
grep -ihE 'no longer applied|deprecat|ignoring|unknown key' "$ROOT/logs/gateway.log" 2>/dev/null | tail -15

sec "PLUGINS: registered vs config's enabled list"
hermes plugins list 2>&1 | grep -iE 'enabled|disabled' | head -25
echo "--- config says enabled: ---"
grep -A8 '^  enabled:' "$H/config.yaml" 2>/dev/null | sed -n '2,10p'

sec "PLUGIN BACKING SERVICES (enabled plugin != running service)"
for port in 8123 7437; do
  ss -tlnp 2>/dev/null | grep -q ":$port " && echo "  ok   :$port listening" || echo "  DEAD :$port nothing listening"
done
for host in homeassistant.local; do
  getent hosts "$host" >/dev/null 2>&1 && echo "  ok   $host resolves" || echo "  DEAD $host no DNS"
done

sec "MEMORY BUDGET (limit comes from config.yaml)"
grep -E 'memory_char_limit|user_char_limit' "$H/config.yaml" 2>/dev/null
wc -m "$H"/memories/MEMORY.md "$H"/memories/USER.md 2>/dev/null
echo "--- all profiles ---"
for p in "$ROOT"/profiles/*/; do
  printf '%-10s %s\n' "$(basename "$p")" "$(wc -m < "$p/memories/MEMORY.md" 2>/dev/null || echo -)"
done

sec "AUX MODELS NAMED IN CONFIG (probe the wire before trusting)"
grep -nE '^\s*(model|provider): ' "$H/config.yaml" 2>/dev/null | grep -vE '^\s*#' | head -20

sec "state.db SIZE + biggest tables"
du -sh "$ROOT"/profiles/*/state.db "$ROOT/state.db" 2>/dev/null
db="$H/state.db"
if [ -f "$db" ]; then
  sqlite3 "$db" "SELECT name, ROUND(SUM(pgsize)/1048576.0,1) mb FROM dbstat GROUP BY name ORDER BY mb DESC LIMIT 8;" 2>/dev/null
  echo "--- sessions by month ---"
  sqlite3 "$db" "SELECT strftime('%Y-%m',started_at,'unixepoch','localtime'), COUNT(*), SUM(message_count) FROM sessions GROUP BY 1 ORDER BY 1;" 2>/dev/null
fi

sec "PRUNE GATE (retention is inert when auto_prune is false)"
grep -A3 '^sessions:' "$H/config.yaml" 2>/dev/null

sec "GATEWAY STATE RESIDUE (dead pid = stale file)"
for f in "$ROOT/gateway_state.json" "$H/gateway_state.json"; do
  [ -f "$f" ] || continue
  pid=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('pid'))" "$f" 2>/dev/null)
  ver=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('code_version'))" "$f" 2>/dev/null)
  if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then st="alive"; else st="STALE"; fi
  printf '%s  pid=%s (%s)  code_version=%s\n' "$f" "$pid" "$st" "$ver"
done

sec "LOG ERROR RECURRENCE (date the pattern before calling it live)"
grep -ihE 'compression.*(fail|error)|Failed to load plugin|Traceback' "$ROOT/logs/errors.log" 2>/dev/null \
  | cut -c1-10 | sort | uniq -c | tail -10

sec "SCHEDULED WORK (idle cron/kanban is fine; orphans are not)"
hermes cron list 2>&1 | head -5
sqlite3 "$ROOT/kanban.db" 'SELECT COUNT(*) FROM tasks;' 2>/dev/null | sed 's/^/kanban tasks: /'

sec "DISK"
df -h "$HOME" | tail -1
du -sh "$ROOT" 2>/dev/null

printf '\nSweep complete. Nothing was modified.\n'