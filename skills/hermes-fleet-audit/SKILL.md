---
name: hermes-fleet-audit
description: "Audit the whole Hermes fleet: skill inventory per profile, drift, real usage, memory and plugins. Trigger: the object is the fleet, or a periodic sweep. NOT a single profile (hermes-profile-audit) and NOT how to use Hermes (hermes-agent)."
version: 1.0.0
author: Bastian Berrios, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  # `internal: true` oculta la skill del descubrimiento normal: `npx skills add`
  # no la instala. Solo entra con `--skill <nombre>` o INSTALL_INTERNAL_SKILLS=1.
  # Es lo que hace que el paquete publico del repo no lleve las skills de Hermes.
  internal: true
  hermes:
    tags: [hermes, audit, fleet, profiles, skills, memory, plugins, verification]
    related_skills: [hermes-agent, hermes-profile-audit]
---

# Hermes Fleet Audit

## Overview

Audit the whole fleet — every profile's skills, memory, plugins and config —
against what is actually running. The four profiles are independent islands:
`aura`, `codehak`, `mingo` and the root `default` share the gateway process but
**nothing else**. No live config inheritance, no skill inheritance, no memory
inheritance. What one profile has, another does not, and only a sweep finds out.

**Every finding in the report must come from a command you ran.** A config key
that parses is not evidence that anything works.

## En la cadena

Fase 3 — Verificación. Condicional: se dispara cuando se audita el estado del
fleet completo — después de un `hermes update`, cuando un perfil se comporta
mal, o en un barrido periodico.
Orden completo: [`CHAIN.md`](../fleet-conventions/CHAIN.md).

## When to Use

- "Revisa mis agentes / el fleet / todas las skills"
- After a version bump (`hermes update`) — deprecation drift surfaces here first
- A profile misbehaves and you do not know which one
- Before publishing or distributing skills across the fleet

**Don't use for:** auditing a single profile's internals (→ `hermes-profile-audit`);
auditing installed third-party agent CLIs (→ `agent-stack-footprint-audit`);
updating the binaries (→ `ai-agent-cli-update-cycle`).

## The three facts that make or break a fleet audit

**1. Each profile is its own `HERMES_HOME`.** `~/.hermes/profiles/<name>/`
with its own `config.yaml`, `memories/`, `plugins/`, `cron/`, `logs/`, `state.db`.
One gateway process serves all of them. A command without `-p` reads the root.

**2. The root's skills are invisible to the named profiles.** `~/.hermes/skills/`
is the *default* profile's tree. `aura`, `codehak` and `mingo` each have their
own `skills/` directory. A skill in the root tree needs a symlink into the
profile to be usable there. This is the single most common silent gap.

**3. Profile plugin directories are not shared.** A plugin installed at root
`~/.hermes/plugins/` is invisible to `~/.hermes/profiles/<name>/plugins/`. A
profile's config can name a plugin that exists in the fleet but was never
installed *for that profile* — and it fails silently to a fallback.

## Procedure

### 1. Inventory: what each profile actually has

```bash
for p in default aura codehak mingo; do
  home=$([ "$p" = default ] && echo ~/.hermes || echo ~/.hermes/profiles/$p)
  echo "=== $p ==="
  ls -1 "$home/skills" 2>/dev/null | head -40
done
```

**Use `hermes -p <name> skills list`, not `HERMES_HOME=... hermes`.**
`terminal.auto_source_bashrc` makes the shell init re-export `HERMES_HOME`,
which overrides the inline assignment, so every profile silently reports the
same home. Always pass `-p` explicitly.

### 2. Find the drift: same skill, different content

```bash
# misma skill en varias ubicaciones -> comparar hashes
for p in aura codehak mingo; do
  find ~/.hermes/profiles/$p/skills -name SKILL.md 2>/dev/null \
    -exec sha256sum {} \; | sed "s|$HOME|~|"
done | sort -k2
```

A skill whose hash differs across profiles is drift: two copies that will
diverge silently from here. The fix is a single source of truth plus a
symlink, not a copy.

**Read the diff before choosing a winner.** In practice the losers are usually
(a) a *truncated description* that lost its trigger, or (b) a cosmetic refactor
of a bundled script. Neither is worth a fork. The winner is the one with the
stronger trigger and the newer upstream semantics.

### 3. Which skills does the fleet actually use?

**Do not trust the usage registry.** It counts a skill as "used" on paths that
never opened it. The ground truth is the message log:

```bash
sqlite3 ~/.hermes/profiles/<p>/state.db \
  "SELECT tool_calls FROM messages WHERE tool_calls LIKE '%skill_view%';"
```

**Read a disabled skill from disk.** A disabled skill is invisible to the
loader — it is not in `skills_list` and `skill_view` refuses it — but the file
is still there. `~/.hermes/skills/hermes-skill-activation/scripts/disabled_skills.py
--profile <p>` lists every disabled skill with its path.

### 4. Verify the audit claims

```bash
hermes -p <p> plugins list --plain --no-bundled   # real plugin state
hermes -p <p> config get plugins.enabled           # what the config claims
```

**`plugins list` without `--no-bundled` shows ~60 rows marked `enabled` for
every profile** — those are bundled and opt-in, never loaded. Never treat that
list as the user's active plugins.

**A configured `<platform>:` block proves only that config exists** —
credentialed (token in `.env`) and live (gateway reports connected) are
different states, and only the third means a message will be delivered.

## Report contract

1. **Rotos** — silently costing money, silently degrading, or failing every call
2. **Avisos** — configured but inert, unbounded growth, cosmetic residue
3. **Verificado OK** — one line each, so the user can see what was actually checked
4. **Qué falta** — the ordered fix list, naming any decision you need from them

**State plainly what could NOT be verified live.** Close by naming what you did
not change: a skill left alone because it is core, in active use, or riskier to
remove than to keep is part of the deliverable.

**Never mark a symptom resolved unless it was re-tested after the change.** Say
"unverified" plainly when a fix landed but the original failure has not
reproduced since.

## Pitfalls

- **Diagnose with numbers before proposing fixes.** If the task states symptoms
  or timings, measure each one and put asserted-vs-measured in a table up
  front; when the stated numbers are wrong, say so plainly instead of
  optimising toward a number that was never real.
- **Audit every profile, not just the active one.** `hermes -p <name>`.
- **Injected memory is a list of claims to verify, never evidence about the
  system** — it caches version-pinned facts (versions, plugin lists, item
  counts) that rot silently. Every one is settled with a live command; see
  `references/memory-and-config-audit.md`.
- **Never claim prompt/context cost from a disk or snapshot count alone** — a
  skill the host cannot load is filtered out at render time, so it costs disk
  and nothing else.
- **A symlink to a bundled skill freezes it.** The sync manifest tracks the
  origin hash per profile; a symlinked copy hashes differently and reads as
  "user-modified" forever, so `hermes update` stops updating it. Symlink only
  skills that are NOT in `.bundled_manifest`. For a bundled skill, the fix is
  `hermes skills reset <name>` (re-baseline) or moving the customization into
  its own skill.
- **Never hand-edit `config.yaml` for the user** — use `hermes config set KEY
  VAL`; a stray indent can corrupt the file and break the live gateway. Note
  that `config set` on a list key replaces the WHOLE list, so read it first
  with `config get` and confirm the write landed.
- **A scan for a forbidden character class will false-positive on the note
  that documents the rule.** Scope automated scans to files being shipped, and
  hand-check the documentation that names the pattern.
- **Symlink chains hide skill and config dirs from `find` and `os.walk`** — a
  profile skill dir that is a symlink into a shared tree reads as missing to a
  non-`-L` find while the loader resolves it fine. Use `readlink -f` plus a
  `SKILL.md` existence check on the resolved target before reporting absence.

## References

- `references/skill-library-audit.md` — what each profile has, which skills are
  used, which are broken or duplicated, and how to tell a used skill from a
  merely-installed one.
- `references/memory-and-config-audit.md` — persistent memory and config drift:
  stale facts, char-budget overflow, connected-vs-configured platforms, and the
  repair that follows.
- `references/profile-plugin-audit.md` — plugin load and startup time across
  all profiles; `/api/status` or `/api/model/info` timing out at boot.
- `scripts/audit-profiles.sh` — the mechanical sweep (read-only): one command
  that prints the per-profile skill inventory, the drift map, and the usage
  counts. It reports candidates, it does not decide which are findings.

## Verification

The audit is done when: every profile's skill inventory is known and its drift
is either resolved or explicitly listed; every disabled skill that the fleet
actually needs has a documented path; every factual claim about plugins,
memory and config is backed by a command output; and the report names a verdict
plus, if applicable, a decision with options.
