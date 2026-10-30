---
name: hermes-profile-audit
description: "Audit ONE Hermes profile: declared config against reality, plugins, memory and logs. Trigger: the object is a single profile. NOT the whole fleet (hermes-fleet-audit) and NOT how to use Hermes (hermes-agent)."
version: 2.0.0
author: Bastian Berrios, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, audit, config, memory, plugins, gateway, state-db, verification]
    related_skills: [hermes-agent-skill-authoring]
---

# Hermes profile audit

## En la cadena

Fase 3 — Verificación. Condicional: se dispara cuando se audita el estado de un
perfil del fleet — antes o después de un `hermes update`, cuando un perfil se
comporta mal, o en un barrido periodico de los cuatro perfiles.
Orden completo: [`CHAIN.md`](../fleet-conventions/CHAIN.md).

Establish what a Hermes profile (`~/.hermes/profiles/<name>/`) is actually doing,
as opposed to what its config claims. A config key that parses is not evidence that
anything works: features get retired while their keys stay, providers alias unknown
model names to expensive defaults, and plugins register tools against services that
are not running. Every finding in the report must come from a command you ran.

## The one fact that makes or breaks the audit

Each profile is its **own `HERMES_HOME`** at `~/.hermes/profiles/<name>/`, with its own
`config.yaml`, `memories/`, `plugins/`, `cron/`, `logs/`, and `state.db`. One shared
gateway process runs from the root `HERMES_HOME` and serves all of them.

**Profile plugins directories are not shared.** A plugin installed at root
`~/.hermes/plugins/` is invisible to `~/.hermes/profiles/<name>/plugins/`. A profile's
config can therefore name a plugin or context engine that exists in the fleet but was
never installed *for that profile* — and it fails silently to a fallback. This is the
single highest-yield thing to check.

**Scope every command to the profile.** Prefix with `export HERMES_HOME=~/.hermes/profiles/<name>`
or `hermes` reads the root config and you audit the wrong thing. Criterion: the profile
path appears in the command's output.

## When to Use

- "revisa mi Hermes / audítalo / dime si todo está en orden"
- Before or after a version bump (`hermes update`) — deprecation drift surfaces here first
- When a profile misbehaves: compression silently degrading, `state.db` growing, one plugin's tools always failing
- Periodic sweep across a multi-profile setup

**Don't use for:** auditing which third-party agent CLIs are installed
(→ `agent-stack-footprint-audit`); updating the binaries (→ `ai-agent-cli-update-cycle`);
auditing or setting up the shared Kanban board, which lives in `~/.hermes/kanban.db`
outside any profile dir (→ `hermes-kanban-orchestration`).

## Procedure

`scripts/profile_audit.sh` runs the mechanical sweep in one shot (read-only, no
writes). Run it first, then work the ranked list by hand — the script reports
candidates, it does not decide which are findings.

### 1. Pin the version, then the static health

```bash
hermes --version        # do this BEFORE judging any key's validity
hermes doctor           # config version, deprecations, tool availability
hermes plugins list     # plugin truth, not the config's own enabled list
```

`hermes doctor` is the highest yield-per-call command in the whole audit. It cannot
produce two classes of finding on its own — inert config keys and lying model names
— which are sections 2 and 5.

### 2. Inert config keys — read the runtime's own startup warnings

A key can be present, parse cleanly, and do nothing, because the feature behind it
was retired upstream. The config file never changes; the runtime just ignores it.
The authoritative detector is the warning the gateway emits per profile at boot:

```bash
grep -iE 'no longer applied|deprecat|ignoring' ~/.hermes/logs/gateway.log | tail -20
```

Two families recur:
- **Retired feature** — the key survives, the timers/codec behind it were deleted.
  Fix is to install the named replacement plugin or delete the block. Never leave it:
  the next reader (human or agent) will assume it works.
- **Gated setting** — a boolean parent switched off makes its subtree inert
  (`sessions.auto_prune: false` renders `retention_days: 90` a no-op). Audit the
  parent, not just the leaf that looks configured.

### 3. Plugins: enabled is not working

```bash
hermes plugins list | grep -iE '<name>'
ss -tlnp | grep <port>; curl -m 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:<port>/
```

An enabled plugin whose backing service is down registers tools that fail on every
call and never surfaces as a boot error. Probe the endpoint before calling it healthy.

### 4. Memory budget

```bash
wc -m ~/.hermes/profiles/<name>/memories/MEMORY.md ~/.hermes/profiles/<name>/memories/USER.md
grep -A6 '^memory:' ~/.hermes/profiles/<name>/config.yaml    # the limits live here
```

Over budget means the next `memory add` is rejected wholesale — report the excess in
characters. Sweep every profile, not just the active one; the limit is per-profile.

### 5. The model name in config is not the model that runs

The highest-value probe in this audit. An auxiliary model (compression, vision, title
generation) is resolved by name against its provider. A name the provider does not
serve is silently aliased to a default, returns HTTP 200, and bills you for the model
you did not choose. Only the response body's `model` field is evidence.
Procedure and the resolution-order trap: `references/aux-provider-probe.md`.

### 6. state.db growth

```bash
du -sh ~/.hermes/profiles/*/state.db
sqlite3 ~/.hermes/profiles/<name>/state.db \
  "SELECT name, SUM(pgsize)/1048576.0 mb FROM dbstat GROUP BY name ORDER BY mb DESC LIMIT 10;"
sqlite3 ~/.hermes/profiles/<name>/state.db \
  "SELECT strftime('%Y-%m', started_at,'unixepoch','localtime'), COUNT(*), SUM(message_count) FROM sessions GROUP BY 1;"
```

Attribute the bytes before recommending a prune. Full-text-search shadow tables
routinely outweigh the `messages` table itself, and they track retention rather than
content size. Tie the number back to section 2's prune finding so the report names the
knob that grows the file.

### 7. Gateway state residue

A profile that ran its own gateway before the multiplexer took over keeps a
`gateway_state.json` holding a dead pid, an old `code_version`, and sometimes a home
path with a typo in it. Inert, but it actively misleads the next diagnosis:

```bash
ps -p <pid-from-json> >/dev/null && echo alive || echo 'stale residue'
```

### 8. Triage: log timestamps bound the claim

Before calling something "recurring", check when it last happened — a warning whose
final occurrence predates the fix is history, and listing it as a live finding costs
the user's attention on a solved problem. `cut -c1-10 | sort | uniq -c` on the grep
output dates the pattern in one command.

## Report contract

Rank by blast radius, not discovery order:

1. **Rotos** — silently costing money, silently degrading, or failing every call
2. **Avisos** — configured but inert, unbounded growth, cosmetic residue
3. **Verificado OK** — one line each, so the user can see what was actually checked
4. **Qué falta** — the ordered fix list, naming any decision you need from them

State plainly what could NOT be verified live. Close by naming what you did not
change: this audit reports, and it waits for the user to pick an item before editing.

## Applying fixes: config.yaml is write-protected to the agent tools

`patch` and `write_file` **refuse** `~/.hermes/**/config.yaml` with "Refusing to write
to Hermes config file… Agent cannot modify security-sensitive configuration". The
sandboxed edit tools cannot be used for any Hermes config edit; route every one through
the CLI, which is the sanctioned channel:

```bash
hermes config set   sessions.auto_prune true        # recognized key
hermes config unset display.tool_progress_overrides # remove a deprecated key
hermes config set --force compression.model MiniMax-M3.1-Flash-Preview
hermes plugins disable homeassistant                # plugin toggles, not config keys
```

`compression.*` is **not** in the recognized-key table, so `hermes config set` refuses
it without `--force` — and `--force` is correct there, because `config get` will warn
"'compression.model' is not a recognized config key" for a key the runtime demonstrably
reads. Absence from the setter's table is not evidence the key is dead; the warning
text is generic. Verify consumption in the runtime source (`grep -rn 'summary_model' agent/context_compressor.py`)
before deciding a key is inert.

Never claim a hook-driven plugin is live because `hermes plugins enable` printed
"Gateway reloaded plugins". Prove it the way the plugin proves itself: import its
`__init__.py` in the runtime venv, call `register()` on a stub context, assert the
expected hook name lands, and call its own reader to confirm it finds THIS profile's
config. Then state plainly that the gateway-side dispatch was not observed, since the
hook's own side effect often lives only in the live process's memory.

## Pitfalls

- **An unknown model name is answered with HTTP 200 and someone else's model.** A
  provider that does not serve the requested name routes the call to a default and
  reports success, so status code, absence of errors, and token accounting all look
  healthy while the spend is wrong. Read the `model` field in the response body of a
  live probe; never infer the serving model from the config string, the provider
  catalog cache, or a 2xx.

- **A retired feature's key outlives the feature and doctor only mentions it once.**
  The warning is emitted per profile at every boot but scrolls out of the log in days.
  Grep the log directly when auditing, or report a key doctor flagged as if it were
  still live — a config the user believes is scheduling resets and is not is worse
  than no config at all.

- **A gated setting reads as configured.** `retention_days: 90` sitting under
  `auto_prune: false` looks like a policy and enforces nothing. When auditing any
  numeric threshold, walk up to the boolean that enables it.

- **A healthy-looking state file is residue.** `gateway_state.json` in a per-profile
  dir can name a dead pid and a two-versions-old `code_version` while the real gateway
  runs multiplexed from the root. Confirm liveness with `ps` before treating any
  state file as current.

- **A name in a usage/registry file is not a claim that the artifact is installed.**
  Registry files routinely carry names for other agents, platform-gated skills, and
  entries whose directories live outside the tree you walked. Diffing a registry
  against one directory produces dozens of phantoms; only names the profile's own
  loader claims are findings. See `agent-stack-footprint-audit` for the full triage.

- **A scan for a forbidden character class will false-positive on the note that
  documents the rule.** If a standing rule says "never emit script X", the memory or
  skill entry recording that rule often contains script X as its worked example.
  Scope automated scans to files being shipped or committed, and hand-check the
  documentation that names the pattern.

- **Symlink chains hide skill and config dirs from `find` and `os.walk`.** A profile
  skill dir that is a symlink into a shared tree reads as missing to a non-`-L` find
  while the loader resolves it fine. Use `readlink -f` plus a `SKILL.md` existence
  check on the resolved target before reporting absence.

- **Do not treat a not-logged-in provider as a finding without naming its blast
  radius.** Optional auth surfaces (a portal, a secondary vendor) legitimately sit
  unconfigured; they only matter if the user depends on that path. Report them as
  availability notes attached to the tool they gate, not as defects.

- **A hook's side effect living in process memory cannot be confirmed by grepping
  state.db.** A plugin that stamps route metadata may target an in-memory store, so
  `grep -rl` over the profile finds only the plugin's own source — and worse, `strings`
  on the WAL can surface the key inside YOUR OWN conversation transcript from the turn
  where you asked about it. A negative or self-referential hit is not evidence either
  way. Import the plugin and call its code, or report the dispatch as unobserved.

- **`enabled` is a config state; the plugin registry is the runtime state.** Read
  `hermes plugins list --plain --no-bundled` (not the Rich table, which truncates
  names into unusable fragments) to confirm what is actually enabled after a toggle.

- **A retention knob that cannot fire yet is still worth enabling, but say so with the
  arithmetic.** `auto_prune: true` + `retention_days: 90` on a store whose oldest row is
  27 days old prunes nothing today — it stops unbounded growth from Nov onward. Report
  it as forward-looking, and give the age so the user knows no space was reclaimed yet.

- **Auditing the root by accident.** `hermes doctor` and `hermes plugins list` read
  `HERMES_HOME`. Without the export they report the root profile and look healthy even
  when the target profile is broken.

- **Trusting the fleet for a profile's plugins.** Root installs are not inherited. Always
  `ls $HERMES_HOME/plugins/` — never the root `~/.hermes/plugins/`.

- **A plugin directory with `.git` but no `__init__.py`** is either a failed checkout OR
  a desktop-only (Electron) package that lives in `~/.hermes/desktop-plugins/` by design.
  If the source tree has `desktop/plugin.js` and `plugin.yaml` describes a desktop
  feature, the Python loader will reject it on every session *and reinstalling will not
  add an `__init__.py`* — the warning is chronic noise, not a broken install. Check the
  sibling `desktop-plugins/` dir for the real copy. A genuinely failed checkout is fixed
  with `hermes plugins install <name> --force`.

- **Cron count from the wrong scope.** `cronjob_manage action='list'` reflects the
  calling profile. A fleet doc claiming "profile X has 0 jobs" must be re-verified before
  repeating it as fact.

- **Never recommend installing a context engine without checking the model supports it.**
  `hermes-snapcompact` renders history into bitmap PNG frames that *vision models* read
  back; with a non-vision model the middle history goes opaque (the engine still runs,
  silently degrading). Check the engine's requirements against the profile's
  `model.default` before offering "just install the plugin". When the fleet runs a
  non-vision model, the right fix is `context.engine: compressor` — aligning config with
  the fallback that already works.

- **Unknown-toolset warnings are often benign, but verify with a real delta.**
  `hermes config check` flags toolsets it cannot resolve. Measure before editing:
  `get_tool_definitions(enabled_toolsets=[t])` per toolset — one returning 0 tools (retired
  `messaging`, `moa`) can be dropped from `platform_toolsets.cli`, but first confirm it
  contributes nothing by diffing the tool-name set with and without it. Import path is
  `model_tools`, not `toolsets`.

- **`hermes config check` is the fastest config linter** — validates YAML, reports
  config-version drift, and flags unknown toolsets in one call. Scope it with
  `HERMES_HOME` or it reads the root. It also dumps a long list of unset optional API
  keys; that is noise, not findings.

## Verification

The audit is done when: every `plugins.enabled` entry has a directory on disk in that
profile; every `not found — falling back` / `Failed to load plugin` line in the log is
either explained or reported; every factual claim in `MEMORY.md` has been checked against
a command output; and the report names a verdict plus, if applicable, a decision with
options.

Exact probe commands and the log-signature triage table are in `references/audit-probes.md`.
