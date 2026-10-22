# Audit Probes and Log Triage

## Topology

```
~/.hermes/                        root HERMES_HOME — shared gateway process lives here
├── hermes-agent/                 code
├── plugins/                      root-level plugins — NOT visible to profiles
├── cron/, kanban.db              fleet-wide
└── profiles/
    ├── aura/     ├── HERMES_HOME per profile: config.yaml, memories/,
    ├── codehak/  │ plugins/, cron/, logs/, state.db, auth.json, .env
    └── mingo/    └──
```

Gateway state file (`~/.hermes/gateway_state.json`) lists `served_profiles` and one platform entry per profile (`<profile>:telegram`). Read it to confirm which profiles are live rather than inferring from directory presence.

## Probe set

Scope the first two; the rest are absolute or already profile-relative.

```bash
# 1. declare the target profile — do this FIRST or you audit the root
export HERMES_HOME=~/.hermes/profiles/<name>

# 2. official health + plugin inventory, correctly scoped
hermes doctor
hermes plugins list --plain --no-bundled

# 3. declared vs installed
ls -la "$HERMES_HOME/plugins/"
grep -A8 '^plugins:' "$HERMES_HOME/config.yaml"

# 4. silent fallbacks — the only trace of a missing plugin/engine
grep -c "not found — falling back\|Failed to load plugin" "$HERMES_HOME/logs/errors.log"

# 5. warning classes by frequency, not recency
grep -oP '(WARNING|ERROR) \K[a-z_.]+:' "$HERMES_HOME/logs/errors.log" | sort | uniq -c | sort -rn

# 6. memory headroom against the declared limit
wc -c "$HERMES_HOME/memories/"*.md

# 7. cron jobs for this profile
cronjob_manage action='list'    # reflects the calling profile only

# 8. secret permissions
stat -c '%a %n' "$HERMES_HOME"/.env "$HERMES_HOME"/auth.json "$HERMES_HOME"/config.yaml

# 9. vault artifacts the profile writes
git -C <vault> status --short
stat -c '%y %n' <vault>/<profile-notes>/*.md | sort
```

## Data-integrity scan (CJK/Cyrillic class of bug)

Scope to the files the profile writes, never the whole vault — the vault documents these bugs in `working-context.md`, pipeline notes, and archives, which are legitimate matches.

```bash
grep -cP '[\x{4e00}-\x{9fff}\x{0400}-\x{04FF}]' <the-profile's-notes>/*.md
```

Zero on every line = clean. Non-zero: print each match with context before calling it a finding —

```bash
grep -noP '.{0,25}[\x{4e00}-\x{9fff}\x{0400}-\x{04FF}].{0,25}' <file>
```

## Log-signature triage

| Signature | Meaning | Action |
|---|---|---|
| `Context engine 'X' not found — falling back to built-in compressor` | `context.engine` names a plugin absent from this profile | Real finding. Either `hermes plugins install X` per profile, or set the engine to the built-in default |
| `Failed to load plugin 'X': No __init__.py` | Partial checkout in a profile's plugins dir | Real finding, belongs to that profile. `hermes plugins install X --force` |
| `Failed to load plugin 'X': dictionary changed size during iteration` | Bundled plugin load race | Usually transient; report once, not per occurrence |
| `Sticky ... path failed` / `Dual-stack ... failed` / `Using sticky IPv4` | Platform reconnect churn, self-heals | Benign. One line or omit |
| `Discovering ... fallback IPs via DNS-over-HTTPS` / `Connecting ... (attempt 1/8)` | Normal (re)connect sequence | Benign. Omit |

A signature that repeats hundreds of times is chronic config drift, not an incident — the fix is a config line, and the count is the argument for fixing it.