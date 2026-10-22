# Skill Library Audit (multi-profile)

Procedure for answering "which skills do I have, which does each profile use, are any
broken" with real evidence instead of guesses. Every claim in the report must trace
to a file on disk, a JSON tracker, or a command you actually executed.

## When to Run

- "audit my skills", "which skills am I using", "clean up my skills"
- prompt bloat: too many skills listed, suspect dead weight
- deciding whether a profile still earns its keep
- after a profile was added, removed, or had its `$HERMES_HOME` changed

## Step 0 — Resolve the real HOME per profile

`~/.hermes/skills` is the bundled stock tree. Each profile has its OWN seeded copy at
`$HOME/.hermes/profiles/<name>/skills`. Auditing the default tree tells you nothing about
what a profile loads.

```bash
for p in aura codehak mingo; do
  echo -n "$p => "
  hermes -p $p skills list 2>&1 | grep -E "enabled," | tail -1
done
```

`HERMES_PROFILE` in the shell may point at a different profile than the one you are
talking to; `hermes -p <name>` is unambiguous. Check `HERMES_HOME` too — a session can
have it set to a profile while the CLI defaults elsewhere.

**Always pass `-p`.** A shell with `HERMES_HOME` already pinned to one profile makes
`hermes skills list` report that profile's tree for every invocation, so a loop over
profile names silently returns one answer N times — and the identical numbers read as
confirmation rather than as the bug. If two profiles report byte-identical counts, suspect
the env before concluding they are symmetric. `--json` does not exist on this subcommand;
parse the box-drawing table instead.

**A gateway restart deletes the prompt snapshot.** It is regenerated on next session
start, so a snapshot path that existed at audit time can be gone later — fall back to
`hermes -p <name> skills list` rather than failing the step. The disappearance is a
symptom, not a defect to report.

## Step 1 — Inventory on disk

Walk `$PROFILE_HOME/skills/` for `*/SKILL.md`, excluding dot-dirs (`.archive`,
`.curator_backups`, `.hub`, `.locks`). Count `.archive/` separately: those are
dead weight, never loaded, but still consume disk.

Completion criterion: per-profile loaded count AND archived count printed separately.

## Step 2 — Usage from the tracker, not the DB

`$PROFILE_HOME/skills/.usage.json` is the authoritative per-skill record:
`use_count`, `view_count`, `patch_count`, `last_used_at`, `state` (`active`/`archived`).

```python
import json
u = json.load(open(f"{profile_home}/skills/.usage.json"))
for n, d in sorted(u.items(), key=lambda kv: -kv[1].get("use_count", 0)):
    print(n, d["use_count"], d["last_used_at"], d["state"])
```

Pitfalls:
- **The tracker lists names that are no longer on disk** (archived, deleted, or never
  seeded into that profile). Those are phantoms — do not report them as installed.
- **`state.db` is a fallback, not the primary.** `skill_view` arguments live inside the
  assistant rows' nested `tool_calls` JSON, and the DB only covers one profile. Parsing it
  is fine for cross-checking, but the counts will under-report against the tracker.

## Step 3 — Cross-profile divergence

Hash `SKILL.md` by relative path across every profile plus `~/.hermes/skills`. Same
relative path, different hash → divergence. Also compare body size: a profile whose copy
is materially LARGER than stock almost always carries hand-written lessons the others
lack — that asymmetry is the finding worth reporting, not the hash itself.

Completion criterion: a decision item per divergence (backport the richest version, or
accept and document it deliberately).

## Step 4 — Mechanical health (execute, never eyeball)

```bash
# every shell script parses
find "$SKILLS" -name '*.sh' -exec bash -n {} \;          # collect failures
# every python script compiles
find "$SKILLS" -name '*.py' -exec python3 -m py_compile {} \;
# broken symlinks (a bare -type l lists valid links too)
find "$SKILLS" -type l -xtype l
```

Plus frontmatter checks: parses as YAML, has `name` + `description`, `name` matches its
directory. Plus every `](references/...)` link in the body resolves on disk.

## Step 5 — Content traps that only surface on execution

| Trap | Why it bites | Rule |
|---|---|---|
| `find ... -not -path '*/musl*'` | `*/musl*` matches path COMPONENTS; a file named `sharp-linuxmusl-x64-0.35.node` has no component equal to `musl`, so it is NOT excluded | substring filters must not be component-anchored: `-not -path '*musl*'` |
| `ls "$d"uv.lock "$d"requirements*.txt` | string concatenation only yields `/path/uv.lock` when `$d` already ends in `/` | always `"$d"/uv.lock` |
| hardcoded absolute home path in a script default | survives a username rename as a path that never existed | make it `${OLD_HOME:-}` and empty by default |
| CJK glyphs in skill files | the `cjk_sanitizer` plugin transforms chat output only — it never touches file contents | `grep -rP '[\x{4e00}-\x{9fff}]' "$SKILLS"` before shipping any skill file |
| `prerequisites: {commands: [...]}` | the runtime gates on `env_vars` only; a `commands` key is silently inert, so the skill reports `available` while the binary is absent | declare `prerequisites.env_vars` / `required_environment_variables` |
| `hermes skills list-modified` counts | it reports names from the default stock tree, so a profile's count includes skills that profile never had | cross-check every reported name against that profile's own disk |
| apparent skill size | a registry index JSON cached under `skills/.hub/index-cache/` can dwarf every real skill combined | attribute disk by subdir before reporting bloat |
| `platforms: [macos]` skill counted as prompt bloat | the runtime re-checks platform compatibility on every prompt build and drops incompatible entries from the listing, so they cost disk but no context | count prompt cost over platform-compatible skills only; see Step 6 |

**Run any audit script you are auditing against a known-true baseline before reporting
its numbers.** A false-positive-heavy filter turns "34 broken artifacts" into "1 broken
artifact" — re-run with the filter corrected and quote both counts so the user can see
the filter was the bug, not the system.

**A linter that flags most of the corpus is a broken linter, not a broken library.**
Before reporting a style check's hits as defects, run it against the upstream/stock
copies, which are known-good. A check that condemns 99% of the vendor tree is
measuring your house style, not its quality — report it as a note or drop it.

**Exclude designed-to-fail files before counting failures.** Artifacts named `stub.*`,
`test.*`, or shipped only as a build input cannot load by design; `dlopen` on one always
errors and becomes a permanent phantom in the count. Filter by name first, then report.

## Step 6 — Prompt cost

The skill-list block injected into the system prompt is the recurring cost: measure it as
`sum(len(name) + len(description))` over the snapshot, **filtered to skills this host can
actually load**. Separately, any SKILL.md over ~20KB enters the context whole on
`skill_view` — the two largest skills are usually the two most used, which makes them the
highest-value refactor targets.

**The snapshot lists every skill on disk; the prompt shows only the compatible ones.**
Do not call a skill "prompt bloat" from a snapshot count alone — a `platforms:` mismatch is
already filtered at render time, so charging the user for it is a false finding and the
correction costs a whole round trip. The filter runs per build, not at snapshot time
(`agent/prompt_builder.py` re-evaluates `skill_matches_platform_list(...)` on every prompt
so host facts stay fresh even from a cached snapshot), and an incompatible entry is marked
`visible: False` and dropped from the listing entirely.

To count real prompt cost, intersect with `skill_matches_platform_list(platforms)` before
summing. Disk savings are real and separable from prompt savings — report them as two
separate numbers, because "the 4 macOS skills are dead weight" and "the 4 macOS skills
inflate every prompt" are different claims and only the first survives checking.

## Step 7 — Prerequisite reality check

`shutil.which()` every binary named in a skill's frontmatter and in its prose. Filter
substring false positives by reading the line: `sq` matches `sq(n)` in a p5js maths table,
`whisper` matches a CSS shadow name. Report a missing prerequisite as a fact about the
machine, not as a defect of the skill.

## Step 8 — The library edits itself while you audit

The curator patches skills on its own interval, and a gateway restart or upgrade reseeds
profiles mid-session. Findings can be stale before you finish reporting them.

**Re-read every file immediately before patching it.** A `patch` whose `old_string` no
longer matches is the signal, not an obstacle — it means the bytes changed under you.
Re-read, diff against your backup, and decide whether the remaining defect still exists.

**Attribute every fix in the report.** State which corrections you made and which another
process made while you worked. Claiming a fix you did not apply, or silently absorbing one
into your own list, misreports what happened — the user needs to know whose change to
trust.

**Re-derive counts at report time.** If the gateway restarted or reseeded, per-profile
enabled counts and the prompt snapshot have changed. The numbers you collected 40 tool
calls ago are not the numbers on disk now.

## Step 9 — Editing under the user's standing rules

- **`gio trash <path>`, never `rm`** — `trash`/`trash-put` do not exist on this system.
  Everything you remove goes to `~/.local/share/Trash/files/` and stays recoverable.
- **Back up before the first edit** with `cp -a` into the profile's `cache/` dir, then
  `diff` the backup against the file after your write to prove you changed only what you
  intended.
- **Never edit a skill the user actually uses** without saying so first. High
  `use_count` means the content is load-bearing — fix the file in place, and report the
  diff rather than restructuring it.
- **Pruning is the user's call.** Disable, don't delete. Present never-used and
  platform-mismatched candidates as a table and stop — a skill with 0 uses in one
  profile may be load-bearing in another, and the user may keep one "por si acaso"
  on a profile that never touched it.

**Check the on-disk state before assuming a skill is active.** A disabled skill keeps its
content as `SKILL.md.disabled`, so a plain `find -name SKILL.md` undercounts the tree and
`hermes skills list` shows it absent — both mean "not loading", not "not there". Diff the
per-profile copies against each other rather than assuming one profile's layout: the same
skill can be live in one profile and `.disabled` in another, and treating a disabled
directory as active work is wasted effort.

**Removing the last skill in a category leaves an orphan.** `DESCRIPTION.md` describes the
category for the prompt and survives its skills; with none left it advertises nothing.
When the final skill goes, check whether the category dir now holds only
`DESCRIPTION.md` and trash the whole dir. Grep the remaining skills for the removed names
(`related_skills`, cross-links) before finishing — a dangling `related_skills` entry is a
reference the next session will try to resolve.

## Step 10 — Executing the prune

Read `ESSENTIAL_SKILLS` in `agent/skill_utils.py` before choosing candidates: it is
subtracted from the disabled set on every read, so its members cannot be disabled from
any surface and including one silently no-ops.

`skills.disabled` is a WHOLE-LIST REPLACE, not an append. `hermes config set
skills.disabled '<json array>'` overwrites whatever was there, so union the pre-existing
entries back in before writing or you silently re-enable what the user disabled on
purpose:

```python
prev = yaml.safe_load(open(f"{profile_home}/config.yaml"))["skills"].get("disabled") or []
names = sorted(set(candidates) | set(prev))          # union, never replace
subprocess.run(["hermes", "-p", prof, "config", "set", "skills.disabled", json.dumps(names)])
```

**A profile that never had the key shows its whole list as "added" in a diff** — the
diff length is not a double-write. Confirm with `yaml.safe_load` that `skills` holds
exactly one `disabled` key and no `platform_disabled` you did not intend.

**Only ever write to profiles the user scoped.** A profile that is obviously dead
(zero usage, no sessions in weeks) is a decision to put to them, not one to bundle into
a prune of the live ones — when the clarifying question goes skipped, leave that profile
untouched and say so in the report rather than assuming the answer was yes.

Verify after writing, with these three checks and no substitutes:
```bash
hermes -p <profile> skills list                  # pruned rows read "disabled", not absent
python3 -c "import yaml; yaml.safe_load(open('.../config.yaml'))"   # still parses
diff <backup> <config> | grep '^<'               # expect ZERO deleted lines
```
Zero deleted lines is the integrity proof that nothing outside the prune list moved; a
corrupted `config.yaml` takes down the live gateway, so this is not ceremonial.

**The curator already respects `skills.disabled`** (`agent/curator.py` filters its
curated report through `get_disabled_skill_names()`), so pruned skills are not
re-litigated on the next background pass — one pruning pass is enough.

## Step 11 — Sessions leave behind their own artifacts

A session that establishes a repeatable pattern can leave three kinds of duplicate
documentation of that same pattern, none of which the user asked for:

1. **Curator-synthesized skills.** A background pass authors `SKILL.md`s *about* the work in
   progress; they appear in `skills_list` and `npx skills list -g` indistinguishable from
   hand-written ones. Compare the skill's creation timestamp against the session: a skill born
   during the session, describing the session's own output, is an artifact.
2. **Notes inside the profile's own `AGENTS.md`/`SOUL.md`** restating what the repo now owns.
3. **Sections in an existing skill** that grew a second, competing copy of a rule that now
   lives elsewhere.

Before finishing, search the library for names describing the work just completed, read what
each says, and consolidate. Salvage first: whatever those artifacts learned that the real
implementation does not record belongs in the implementation's own docs, not in a skill about
building it. Then remove the duplicate through the curator (`hermes curator archive <name>`)
so the ledger and the usage sidecar stay consistent — a hand `mv` into `.archive/` leaves the
ledger claiming the skill is live.

Report the consolidation in the session summary. The user asked for a repo, not a second
description of how to build one.

## Reporting Shape

Tables over prose. Three blocks: **inventory per profile** (loaded / enabled / never-used /
divergent), **errors with proof** (the command you ran and what it returned), **decisions
for the user**. State the method behind each claim in one clause. Offer to fix the
mechanical bugs and propose a pruning plan as a separate next step — do not delete or
disable anything unasked.

**Open the report with a retraction when you got a finding wrong.** A wrong claim costs
the user a full round trip to discover and a second round trip to undo; naming it in the
first lines of the next message — what you said, what is actually true, and how you
checked — is cheaper than letting them find it. Verify a claim about prompt cost or
runtime behaviour by reading the filter in the source before asserting it, not by
inferring from a count: "these 4 skills occupy the prompt" was wrong because platform
compatibility is re-evaluated per build, and the correction was only found by opening
`agent/prompt_builder.py` after the user asked what the skills actually do.

**Ask before pruning, and ask about the whole set, not skill-by-skill.** The user
answers faster and better on one question about a group ("these 3 are email/Google, keep
them?") than on six questions about individual skills. Reserve `clarify` for the
judgement calls — a profile that looks dead, a skill you suspect they still want — and
decide the mechanical part yourself.