# Memory & config drift audit

Use when asked to audit "my context / memory / config", check that the agent's
persistent state is sane, or when the profile's memory looks wrong, full, or
inconsistent with the machine.

Memory is a **cache of version-pinned facts**. Every claim in it was true when
written and rots silently — nothing invalidates a version string, a plugin list,
or an item count when the underlying thing changes. So memory is never evidence
about the system; it is only ever a list of things to go verify.

## The char budget is a hard gate, and the percentage lies

`memory.memory_char_limit` / `memory.user_char_limit` in `config.yaml` are
ceilings, not targets. Over them, the memory system rejects new adds — the
agent silently stops learning mid-session.

**Do not trust the injected header percentage.** It renders as a filled bar, so
an over-limit file reads as "100% full" when it is actually 128% of budget. Only
a raw count settles it:

```bash
H=~/.hermes/profiles/<name>; [ -d "$H" ] || H=~/.hermes   # default profile
for f in MEMORY USER; do
  printf '%s: %s / %s\n' "$f" "$(wc -m < "$H/memories/$f.md")" \
    "$(hermes -p <name> config get memory.${f,,}_char_limit 2>/dev/null || grep -oP "(?<=${f,,}_char_limit: )\d+" "$H/config.yaml")"
done
```

**`wc -m`, not `wc -c`** — the limit is denominated in characters, so counting
bytes invents overflow that does not exist. The gap lands exactly where it hurts:
a memory file quoting Han glyphs (3 bytes per char in UTF-8) plus em-dashes and
arrows measured ~300 chars high, enough to make an already-compliant rewrite look
still-overbudget and send you trimming content you never needed to cut.

Raw count on the file, limit from config — never both from the injected block. Fix
the overflow before auditing anything else: a file at 128% is a finding that
gates every other write, and the obvious cause is that the false facts were never
removed.

## Verify every fact against the live system

Do not reason about which memory claims are *plausibly* stale — check each one.
The claims that rot most often, with the command that settles each:

| Claim type | Settle it with |
|---|---|
| Hermes version | `hermes --version` |
| Enabled plugins | `hermes -p <p> config get plugins.enabled` + `ls $HERMES_HOME/plugins` |
| Project / file counts | `ls -1 <dir> \| wc -l` |
| Tool versions | `<tool> --version` |
| Tool availability | `command -v <tool>` |
| Connected platforms | live gateway state, not `.env` keys |

**Rank findings by how much damage the stale claim causes.** A wrong plugin list
is dangerous, not merely untidy: an agent that reads "plugins: kanban enabled"
spends the session looking for tools that do not exist. A wrong project count is
cosmetic. Lead the report with the dangerous ones.

## Configured is not connected

Three different states get conflated constantly; a `config.yaml` block proves
only the first.

1. **Configured** — a `<platform>:` block exists in `config.yaml`.
2. **Credentialed** — the token is present in `.env`.
3. **Live** — the gateway reports the platform connected.

Only (3) means a message will be delivered. Check credentials and live state
before reporting any platform as working; a `slack:` block with no `SLACK_*` token
in `.env` is a config stub, and a memory line claiming that platform notifies is
false.

**A memory line naming platforms is a claim, not a description** — verify each one
against live gateway state.

## Runtime state files go stale — verify liveness from the process

`gateway_state.json` is written by the gateway at startup and not rewritten on
every event. Long after a restart it can still report `stopped`, an old pid, and
an old `code_version`, and its recorded `hermes_home` path can carry a typo that
no longer resolves. Reading it as current truth produces a confident,
completely wrong liveness claim.

```bash
ps aux | grep -E "hermes.*gateway" | grep -v grep
```

Prefer the live process. When a state file and the process table disagree, the
process table is right and the file is a historical artifact — say so explicitly
rather than reporting what the file claims.

## A correction entry does not neutralise the wrong rule above it

When a fact gets corrected, the fix is appended and the original stays. Reading
in order, the general rule still wins — so a session can act on the stale rule
while the correct entry sits unread below it.

**Remove the wrong line; do not just append the correction.** One rule, stated
once. A memory file holding both "always use X" and "X does not exist here" is
worse than either alone, because which one wins depends on read order.

Generalise this when auditing any standing-rules list: look for entries that
contradict each other, not just entries that are individually false.

## CJK sweep false positives in memory and skill files

Sweeping for CJK contamination across a profile hits `memories/*.md` and skill
files legitimately full of Han glyphs — a memory entry or a skill that documents
the CJK-generation defect quotes the glyphs on purpose. Flagging them as
contamination is a false finding.

Same rule as vault lessons-learned notes (see the vault-maintenance skill):
before treating a hit as generated debris, confirm the file is *meant* to contain
those glyphs. Print the surrounding line and read it; a count alone cannot
distinguish a deliberate quotation from a defect.

Note that a chat-scoped sanitiser plugin does not cover file content — the
disk-level sweep is the only check that does, and it needs the false-positive
filter above to stay usable.

## Repair phase: the write guard, and the trim that does not shrink

Once the user approves the repair, three mechanical traps, in the order they bite.

**Re-read the memory file immediately before overwriting it.** A full-file
`write_file` is refused by a stale-write guard when the only read of that file
happened earlier or before a context compaction — the guard requires a read from
the current task. The refusal names the file and leaves it untouched, so re-read
and write again; do not work around it with blind patching.

**Patching a file with no trailing newline concatenates lines.** The last line of
a memory file frequently has no final newline, so a patch whose `old_string` is the
final entry merges the replacement into whatever follows. Read the file back after
the last edit and confirm the tail survived, instead of trusting the diff.

**Correcting false facts does not reliably shrink the file.** Replacing a short
wrong claim with a longer true one grows it — the real plugin list is longer than
the two stale names it replaces, and an accurate rule carries its "why" inline.
A file can be over budget while every line in it is now true. Re-measure, then cut
genuine redundancy: counts that re-derive from a live command, version strings
bound to re-rot, and pointers duplicating another source of truth. Keep the rules
that prevent expensive mistakes — those are what the budget is for.

**Prefer storing the command over the value for anything re-derivable.** "Version
real via `hermes --version` — no hardcodear" survives every upgrade; a corrected
version string is wrong again at the next release. Same for item counts.

## Repair phase: destructive cleanup is a separate decision

Stale locks and orphaned state files are in scope for the repair, but each class
needs its own check first — a lock is not just an old file, it may be held.

**Check a lock is unheld before removing it:** `fuser <path>` (or `lsof`) must
return nothing. Zero-byte locks with old mtimes are ordinary residue, not evidence
of a stuck process.

**A live ticker touches its own locks every cycle.** A lock whose mtime is
*current* belongs to a running process even though the file is empty — leave it.
An mtime older than that subsystem's last run is the real staleness signal.

**Profile-local copies of shared state files are usually leftovers.** A gateway
state file under a profile directory can predate profiles entirely while the live
one sits at the base home and is rewritten continuously. Compare mtimes across
both locations and read the copy the running process actually owns before calling
anything stale — and confirm the survivor is the live one before deleting.

**Keep config backups that differ from the current config.** `diff -q` each
against its live counterpart: identical ones are safe to drop, different ones are
the only rollback available and cost kilobytes. Say in the report that they were
deliberately left, so silence is not read as an oversight.

Use `gio trash <path>` rather than `rm` for deletions — `trash` and `trash-put` are
frequently absent on Arch-derived systems, and `gio trash` is recoverable from
`~/.local/share/Trash/files/`.

## Report shape

Lead with what is **blocking** (char-budget overflow, dead pointers to things
that do not exist), then false claims ranked by consequence, then internal
contradictions, then stale artifacts. Close with what is verified **clean** — a
sweep that came back empty is a result, and it is cheap to state.

Keep asserted-vs-measured pairs explicit (`says X / actually Y`) so the user can
recheck without rerunning the whole audit.

**Audit means audit.** Report findings and end with a short ranked recommendation
plus an offer to apply it; do not rewrite the memory file inside an audit request
unless the user asked for the repair. Distinguishing "tell me if this is in
order" from "fix it" is the single most consequential decision in this task.