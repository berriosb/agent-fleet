# Multi-profile plugin & startup audit

Use when Hermes feels slow, when a desktop/gateway endpoint times out at boot, or
when the user asks to "audit my agents". Scope is every profile, not just the
active one.

## Four different things people call "a plugin"

Confusing these is the biggest source of wrong audits.

| Concept | Where it lives | How to see it |
|---|---|---|
| **Installed** | `$HERMES_HOME/plugins/<name>/` | `ls $HERMES_HOME/plugins` |
| **Declared** | `plugins.enabled` in config.yaml | `hermes -p <p> config get plugins.enabled` |
| **Loaded** | what actually runs at boot | `hermes -p <p> plugins list --plain --no-bundled` |
| **Bundled** | ships in the source tree, not any profile | `hermes -p <p> plugins show <name>` -> `Source: bundled` |

`plugins list` WITHOUT `--no-bundled` prints 60+ rows marked `enabled` for every
profile - messaging platforms, image/video providers, web backends. These are
opt-in and never load. Treating that list as "the user's active plugins" is wrong
by ~50 entries and sends the whole audit sideways.

The delta between **declared** and **loaded** is the orphan set: entries named in
`config.yaml` that no profile directory provides. The delta between **bundled**
and **installed** is NOT an orphan - `hermes plugins show <name>` is the tiebreak.
A bundled plugin reported `Status: enabled` is real and working even though no
profile directory contains it.

## Pin the profile with -p, never with HERMES_HOME

`terminal.auto_source_bashrc: true` means Hermes sources `~/.bashrc.local` in every
terminal it opens. That file commonly re-exports `HERMES_HOME`, which **overrides an
inline assignment**:

```bash
HERMES_HOME=~/.hermes/profiles/codehak hermes plugins list   # WRONG - reports another profile
hermes -p codehak plugins list                              # correct
```

Symptom of the bug: auditing four profiles returns the same plugin list four times.
Rule: for any per-profile query, pass `-p <profile>`.

## Audit sequence

```bash
# 1. Per profile: declared vs loaded vs installed
for p in default aura codehak mingo; do
  H=~/.hermes/profiles/$p; [ "$p" = default ] && H=~/.hermes
  echo "== $p"
  hermes -p "$p" config get plugins.enabled
  hermes -p "$p" plugins list --plain --no-bundled
  ls "$H/plugins"
done

# 2. Errors per profile (each has its own errors.log)
grep -c "event loop stalled" ~/.hermes/profiles/<p>/logs/errors.log

# 3. Startup time, 3 runs, discard the first (cold import)
for i in 1 2 3; do
  s=$(date +%s%N); hermes -p <p> plugins list --plain --no-bundled >/dev/null
  echo "$(( ($(date +%s%N)-s)/1000000 ))ms"
done
```

`scripts/audit-profiles.sh` runs all of it for every profile at once.

## Removing an orphan entry safely

`hermes config set` on a list key **replaces the whole list**. Naming one entry to
remove silently disables every other entry too.

```bash
# WRONG - also disables prompt-queue, snag-shelf, homeassistant, moshi-hooks
hermes -p aura config set plugins.enabled '["cjk_sanitizer"]'

# RIGHT for an installed plugin - targets one key
hermes -p aura plugins disable prompt-queue

# RIGHT for an orphan with no installed dir - rewrite the full list, then verify
hermes -p mingo config set plugins.enabled '["cjk_sanitizer"]'
hermes -p mingo config get plugins.enabled     # confirm it actually applied
```

`hermes plugins disable <name>` fails with `No plugin named '<name>'` when the entry
was never installed - that is the signal to switch to `config set`.

**Verify every write.** A `config set` can emit only dependency-resolution noise and
apply nothing, with an exit code that does not reflect it. Re-read with `config get`.

A toolset listed in `platform_toolsets` (e.g. `kanban`) is core and survives removal
of a same-named plugin entry - but check `grep -c <name> logs/gui.log` before assuming
the plugin is unused.

## External runtimes a plugin shells out to

A plugin needing an external runtime (`snapcompact` -> Bun for snapshot rendering)
repeats the same warning forever unless the runtime is on the PATH **Hermes sees**.
Installers typically append to `~/.bash_profile` only, which Hermes never sources.

Fix: export it in `~/.bashrc.local`, then prove visibility:

```bash
bash -c 'source ~/.bashrc.local >/dev/null 2>&1; command -v bun && bun --version'
```

If root escalation is unavailable, the user-local installer is the fallback:
`BUN_INSTALL="$HOME/.bun" bash bun-install.sh` (no sudo needed; check
`pacman -Si <pkg>` first - a distro package is usually cleaner when sudo works).

Prove the warning actually stopped by diffing the log rather than trusting silence:

```bash
L=$(wc -l < ~/.hermes/logs/errors.log)
hermes -p default plugins list --plain --no-bundled >/dev/null
tail -n +$((L+1)) ~/.hermes/logs/errors.log | grep -c "<warning text>"   # expect 0
```

## Reading boot timeouts correctly

`Timed out connecting to Hermes backend after 30000ms` on `/api/status` is a
**connect race**, not plugin cost. Compare timestamps in `~/.hermes/logs/desktop.log`:

```
[boot] Starting Hermes backend      <-- t0
HERMES_BACKEND_READY port=NNNNN     <-- t1: total startup = t1 - t0
... Timed out ... /api/status       <-- if AFTER t1, plugins are not the cause
```

The desktop backend port is **ephemeral** - read it from the `HERMES_BACKEND_READY`
line or `ss -ltnp`, never hardcode a port (guessing 8765 makes every probe hang 30s
and looks like the bug you came to diagnose). Verify the live backend directly:

```bash
ss -ltnp | grep hermes
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' http://127.0.0.1:<port>/api/status
```

`event loop stalled Ns (GIL pressure suspected)` is a separate signal and usually
tracks how many profiles boot inside one multiplexed process
(`gateway.multiplex_profiles: true`). Not fixable by disabling plugins.

`dictionary changed size during iteration` in `hermes_cli.plugins` is an upstream
race in the loader, thrown while **building** the plugin list. It names plugins the
user never configured (bundled messaging/provider plugins) and no config change
fixes it. Do not chase it by disabling plugins - say so and move on.

## Report shape

Lead with a table of asserted-vs-measured. If the task's stated numbers are wrong,
say so before proposing fixes. Then per profile: before/after timing, what changed,
what was deliberately left alone and why, and what remains unfixed. Do not report a
timeout as resolved unless it was re-tested after the change.