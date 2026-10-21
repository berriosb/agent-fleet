---
name: pre-push-qa
description: "Use when ANY agent (Codex, OpenCode, Claude Code, Gemini, Antigravity agy, Hermes Agent, terminal) is about to commit or push to GitHub and you want to reduce CI failures before they happen. Pre-push quality gate for non-pi agents. Runs static + tests locally with model-agnostic output. NOT a fit for Pi (gentle-ai) which has its own superior 4R/JD/lens review path. Triggers on: 'commit', 'push', 'fix this before I push', 'make sure CI passes', 'pre-push check', or before opening any PR."
version: 0.1.0
author: codehak
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [qa, ci, pre-push, git, github, agent-agnostic, code-review]
---

# pre-push-qa — local QA gate for any agent

**Why this exists:** You (the user) are running 5+ AI coding agents (Hermes, Claude Code,
OpenCode, Codex, Gemini CLI, Antigravity agy). Each one has its own way of working, but **all of them
land on the same GitHub remotes** where CI can fail for the same reason: lint, types, or
tests not run before push. This skill is the agent-agnostic quality gate that runs in any
agent's context, with no extra API keys and no extra setup beyond a single `npm pkg add`
or `pip install` depending on stack. **Pi / gentle-ai is the one agent where this skill
isn't applied** — Pi already has stronger 4R / JD / lens review machinery and uses that
instead.

**Relationship to other skills** (optional, and not part of this repo — use them only if
they happen to be installed; this skill works standalone):
- `requesting-code-review`: local pre-commit security + reviewer subagent. Heavy, requires a
  fresh subagent. **Use this skill when you want lighter, faster, no-LLM pass.**
- `github`: PR/branch/CI lifecycle; assumes a remote exists. This skill runs **before** that.
- `multi-repo-portfolio-audit`: portfolio-wide lint/TODO sweeps. This skill is single-repo.
- CI/remote: each repository runs its own standard CI checks. This skill acts strictly *before* push.

**Terminal usage:**
`pre-push-qa` can also be run globally from any terminal when symlinked to `~/.local/bin/pre-push-qa`:
```bash
mkdir -p ~/.local/bin
ln -sf "$HOME/Proyectos/agent-fleet/skills/pre-push-qa/scripts/run.sh" ~/.local/bin/pre-push-qa
```
Running `pre-push-qa` in any terminal runs stack detection, linters, tests, security checks, and creates the verification marker.

## En la cadena

Fase 3 — Verificación: los chequeos de lint, tipos y tests.
Fase 5 — Push: el marcador de verificación, que se genera **después** del commit.
Orden completo: [`CHAIN.md`](../fleet-conventions/CHAIN.md).

## When to use this skill

Load `pre-push-qa` whenever any of your agents says one of:
- "I'm going to commit this"
- "push to origin" / "push to main" (trunk-based direct pushes)
- "open a PR"
- "ship this fix"
- "before I push — make sure CI passes"
- also load proactively before `delegate_task` work that will commit, or before running
  `hermes-agent code` with autoCommit=true

**Skip this skill when:**
- The user said "no verification" / "skip review" / "just commit"
- The change is docs-only (whitelist: `*.md`, `*.mdx`, `docs/**`, `**/*.txt`, `.github/ISSUE_TEMPLATE/**`)
- The repo is a sandbox / spike that won't reach a real CI

## Inputs the agent must have

This skill assumes the **executing agent** provides context. Specifically:

| What | Required? | Fallback |
|---|---|---|
| Working directory of the repo | Yes | error |
| Git status / diff | Yes | auto-compute via `git status --porcelain` + `git diff HEAD` |
| Test/lint commands | No | auto-detect from project files (see Step 1 below) |
| API key for LLM review | No | **skip review step** |
| `gh` CLI authenticated | No | skip remote checks |

## Step 1 — The runner detects the stack and picks the commands

The runner is `scripts/run.sh`, in this skill. It detects the stack by reading the project
files below (first match wins) and runs that stack's native tools. It is the only
implementation: do not reimplement the detection inline, because a second copy drifts.

| Marker file | Stack | What the runner does |
|---|---|---|
| `pnpm-lock.yaml` | pnpm | install (frozen), lint, `tsc --noEmit`, tests, build |
| `yarn.lock` | yarn | install (frozen), lint, `tsc --noEmit`, tests, build (each guarded by `package.json`) |
| `bun.lockb` / `bun.lock` | bun | install (frozen), lint, tests, build (each guarded by `package.json`) |
| `package-lock.json` | npm | `npm ci`, lint, `tsc --noEmit`, tests, build |
| `uv.lock` / `pyproject.toml` | python | `ruff`, `mypy`, `pytest` via `uv run` |
| `requirements.txt` / `setup.py` | pip | `ruff`, `mypy`, `pytest` (or `unittest` when pytest is absent) |
| `*.py` with no manifest at all | python | `ruff`, `mypy`, `pytest` from `PATH`; each one is skipped when the tool is not installed |
| `go.mod` | go | `go vet ./...`, `go test ./...` |
| `Cargo.toml` | cargo | `cargo check --all-targets`, `cargo test` |
| `package.json` (no lockfile) | npm | install, lint, `tsc --noEmit`, tests, build |
| `*.tf` | terraform | `terraform fmt -check -recursive` |
| `Dockerfile` / `docker-compose.*` | docker | `hadolint Dockerfile` |
| no code files at all | docs | skips lint/tests |

If none match: `mixed` — the runner does a best-effort pass (npm tests when a
`package.json` exists, plus `shellcheck` over shell scripts).

**Always skip lint/test if the diff only touches:** `*.md`, `*.mdx`, `docs/**`,
`.github/ISSUE_TEMPLATE/**`, `assets/**`, `*.lock` (unless manifest-affecting),
`*.svg`, `*.png`.

The runner takes two flags:

| Flag | What it does |
|---|---|
| `--detect` | Prints the detected stack and exits. Used by the CI to pick setup steps without keeping a second copy of the detection logic. |
| `--scope all\|static\|tests` | Runs the whole gate (default), only lint/types/build, or only tests. The CI uses the last two to split the work across two jobs. A scoped run does not write the verification marker: a partial run does not approve a push. |
| `--update-baseline` | Writes the currently failing tests to the repo's baseline file, so that pre-existing failures stop blocking pushes. |

**Baseline.** A repo can have tests that were already failing before anyone
touched anything. Blocking the push for that leaves the repo unable to push at
all. The baseline file (`pre-push-qa-baseline.txt`, in the repo root) lists the
tests that are already known to fail: only failures *outside* that list block.
It is meant to be committed — it is the list of failures the project decides to
tolerate, and it has to be visible in the PR that adds it.

The TypeScript check runs only when the project has a `tsconfig.json` **and**
`typescript` is installed. There is no `--if-present` flag for `tsc`: that flag
belongs to the script runner (`pnpm run`, `npm run`), and `tsc` rejects it with
`Unknown compiler option`, which used to fail the gate on every TypeScript
repo.

**A tool that is not there is skipped, never a failure.** The gate blocks on
problems it finds, not on tooling the project never asked for. `ruff`, `mypy`
and `pytest` are probed for availability before running; if none of them is
available, the check is reported as skipped. This matters with `uv`: `uv run
mypy` falls back to the PATH and, if the tool is not there either, answers
`Failed to spawn` with exit code 2. Treating that as a failed typecheck made
the same repository pass on a machine with mypy and fail on one without it.

The exception is the **toolchain** of the project: `go`, `cargo`, `terraform` y
`node`. Si el proyecto es de ese tipo y el toolchain no está, el gate no puede
correr nada y el push se bloquea. La diferencia con `ruff` o `pytest` es que
esas son herramientas de calidad: un proyecto puede no usarlas. Un proyecto Go
sin Go instalado no se puede testear.

## Step 2 — Run static + tests (the cheap, fast, free part)

Run the runner against the repo you want to push. It prints every step, exits non-zero if
anything failed, and writes the verification marker only when everything passed:

```bash
# from the repo you want to push, with the skill directory resolved
bash "<skill-dir>/scripts/run.sh"

# or, if the runner was linked into PATH
pre-push-qa
```

Exit 0 means the checks passed and the marker was written to `.git/pre-push-qa-ok`.
Non-zero means it failed and no marker was written — see Step 5.

**If something fails here: STOP and fix it before going to Step 3.** Most CI failures
come from lint or import errors that this step catches.

**For Yarn and Bun**, `lint` and `test` scripts are safely guarded by inspecting `package.json` to prevent failures when a project does not define them.

**For pnpm specifically, MEMORY tells you `pnpm test --run` is rejected** — use the
double-dash form `pnpm test -- --run` or `pnpm vitest run`. This skill's commands above
follow that constraint.

## Step 3 — Optional: AI review

This step is **only run if the user hasn't disabled it**. The agent running this skill performs the review directly using its native reasoning (no external API keys, no external script paths required):

1. Get the diff: `git diff HEAD` (or `git diff --cached` if changes are staged).
2. Apply the review prompt in [`prompts/review.md`](prompts/review.md) **verbatim**. That file is
   the single source of truth: the CI sends the same one through `scripts/review-call.js`, so a
   review in a terminal and a review on the PR apply the same criteria.
3. Post findings as comments in conversation. Do NOT modify code from the review step (auto-fix is a separate step, gated on user approval).

If the running environment lacks an interactive LLM agent → skip Step 3 entirely. The static + tests in Step 2 are the load-bearing part.

## Step 4 — Optional: Auto-fix attempts (HITL by default)

**Never auto-fix without explicit user permission.** When lint or tests fail:

1. Extract the FIRST error from the failing log (≤ 100 lines).
2. Apply the auto-fix prompt in [`prompts/auto-fix.md`](prompts/auto-fix.md) **verbatim**. It carries the hard rules (one file at most, mechanical change only, no configs, no lockfiles, no new dependencies, exact contiguous match) and the JSON contract to answer with. The CI sends the same one through `scripts/auto-fix-attempt.js`.
3. If the proposal is mechanical and safe, propose it to the user. Upon confirmation, apply and commit ONLY that file, under the repo owner's identity (Zero AI Branding).
4. Otherwise, surface the failure to the user and stop.

If the user said "just push it / don't stop on CI failures", skip Step 4 entirely.

## Step 5 — Push guard & Verification Marker

> [!IMPORTANT]
> **CRITICAL TIMING NOTE FOR GIT HOOKS:**
> If consumer repos use the pre-push hook, it verifies that `.git/pre-push-qa-ok` matches the **exact HEAD commit hash** being pushed.
> - If QA is run before creating the commit (e.g. while unstaged or uncommitted), you MUST generate/update the marker **AFTER `git commit` and BEFORE `git push`**.
> - Otherwise, the hook will detect a stale commit hash and block the push (`STALE MARKER ERROR`).

Before pushing, the agent must verify and execute:

1. **Confirm checks passed:**
   - [ ] No sensitive `.env` files tracked in git:
     `git ls-files | grep -E '(^|/)\.env(\.[^/]*)?$' | grep -vE '\.(example|sample|template|test|ci|defaults)$'`
   - [ ] No private keys tracked in git:
     `git ls-files | grep -E '\.(pem|key|pkcs12|pfx|id_rsa|id_ed25519)$'`
   - [ ] `git status --porcelain` is clean OR the only changes are the approved auto-fix from Step 4
   - [ ] All lint commands in Step 2 exited 0
   - [ ] All typecheck commands in Step 2 exited 0
   - [ ] All test commands in Step 2 exited 0
   - [ ] Build check passed (`build --if-present` exited 0)
   - [ ] CI Secret Independence: Tests do NOT depend on unmocked local-only environment variables missing from CI
   - [ ] User has approved the commit message (or agreed to auto-generated `[skip ci]` prefix)

2. **Generate the Git Hook Verification Marker (post-commit):**
   If the local environment uses the pre-push hook (`examples/pre-push.sh`), create the marker immediately before running `git push`:
   ```bash
   GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || echo .git)"
   CURRENT_HEAD="$(git rev-parse HEAD 2>/dev/null || echo "ok")"
   if [ -d "$GIT_DIR" ]; then
     echo "$CURRENT_HEAD" > "$GIT_DIR/pre-push-qa-ok"
   else
     echo "$CURRENT_HEAD" > .pre-push-qa-ok
   fi
   ```
   *(Writing inside `.git/` avoids untracked file pollution and keeps `git status` clean in consumer repos).*

3. **Execute Push:**
   Run `git push origin <branch>`. The pre-push hook verifies the commit hash and consumes the marker.

**Refuse to push** if any check fails. Surface the failure and let the user decide.

## Step 6 — PR Creation & Commit Hygiene (Zero AI Branding)

When creating commits or opening Pull Requests (`gh pr create`), the agent **MUST** enforce clean, human-grade standards:

### 1. Zero AI Footprint / Prohibited Branding
- **NEVER** include AI self-attribution or marketing tags in commit messages, PR titles, or PR descriptions:
  - ❌ Do NOT write: `Generated by Claude Code`, `Created with Codex`, `Authored by Gemini`, `🤖 AI-generated PR`, etc.
  - ❌ Do NOT add AI git trailers: `Co-Authored-By: Claude <...>`, `Co-Authored-By: Codex <...>`, etc.
- All commits and PRs must read as professional, human-authored contributions under the repo owner's identity.

### 2. PR Title Format
- Follow Conventional Commits: `<type>(<optional-scope>): <imperative description>`
- Concise (< 72 characters), lowercase type, no period at the end.
- Examples:
  - `feat(api): add oauth refresh token endpoint`
  - `fix(db): resolve connection pool leak on timeout`

### 3. PR Body Structure
Always provide structured, factual technical context:
```markdown
## Summary
[1-2 sentences explaining what problem is solved and why]

## Changes
- [Concise bullet of change 1]
- [Concise bullet of change 2]

## Verification
- Lint / Static: [e.g. `uv run ruff check .` passed]
- Tests: [e.g. `pnpm test` passed (15/15 tests)]
```

## Outputs the agent should give back

After this skill runs, the agent reports back to the user (in this exact shape —
the `pre-push-qa` shape is contract for any agent to fill in):

```
PRE-PUSH QA VERDICT: PASS | FAIL
  Stack: <detected>
  Lint:  <pass|fail> — <one-line summary>
  Types: <pass|fail|skipped> — <one-line summary>
  Tests: <pass|fail|skipped> — <one-line summary>
  AI review: <passed|n findings|skipped>
  Auto-fix attempts: <n committed|n declined|n skipped>
```

A "FAIL" verdict blocks push unless the user has explicitly requested force-push.

## Cross-agent invocation table

| Agent | How to invoke this skill |
|---|---|
| **Hermes Agent** | Load with `skill_view(name='pre-push-qa')`. Run steps verbatim. |
| **Claude Code** | Add the SKILL.md to `~/.claude/skills/pre-push-qa/SKILL.md` — Claude auto-loads from `~/.claude/skills/`. |
| **OpenCode** | Symlink the directory into `~/.agents/skills/pre-push-qa/`. OpenCode scans `~/.agents/skills/` and `~/.claude/skills/` as external skill roots; `~/.config/opencode/skill(s)/` is the newer local path and is NOT required for global installs. |
| **Codex CLI** | Drop into `~/.codex/skills/pre-push-qa/`. Codex picks up skills per `~/.codex/skills/`. |
| **Gemini CLI** | Symlink into `~/.gemini/skills/pre-push-qa/`. Gemini CLI auto-discovers. |
| **Antigravity CLI (`agy`)** | Google AGY CLI. Discovers workspace skills from `.agents/skills/<name>/SKILL.md`. To enable global discovery from `~/.agents/skills/`, ensure `~/.gemini/config/skills.json` declares `{"entries": [{"path": "~/.agents/skills"}]}`. |
| **Pi / gentle-ai** | ⚠️ **DO NOT install in Pi.** Pi has its own 4R/JD/lens review pipeline which is strictly better than this skill's Step 3. This skill is **not** the right tool for Pi. |
| **Codex/Claude/OpenCode agents invoked by `delegate_task` from Hermes** | The parent Hermes should run pre-push-qa locally before the delegated work returns; failing that, run it on the subagent's output before committing. |

**Pi / gentle-ai is intentionally NOT in this list.** Pi already has 4r-review chain, JD
judges, and four review lenses (risk/reliability/resilience/readability) — they cover
review with more depth than a one-shot generic AI review would. Inside Pi, use
`/4r-review` or the JD agents directly.

## Installation (one-time, all agents)

### Option 1: Via `skills.sh` (Recommended)
Installs automatically across all supported agents (Claude Code, Antigravity `agy`, Cursor, Codex, Gemini CLI, OpenCode, Copilot, Cline, etc.):
```bash
npx skills add berriosb/agent-fleet -g
```

### Option 2: Manual symlink / clone
```bash
SRC="$HOME/Proyectos/agent-fleet/skills/pre-push-qa"
# Or if using Hermes profile (SKILL.md + scripts/ + examples/ + prompts/ all resolve):
# SRC="$HOME/.hermes/profiles/codehak/skills/software-development/pre-push-qa"

# Link the WHOLE DIRECTORY, not just SKILL.md. Agents that receive only SKILL.md
# cannot reach scripts/run.sh, examples/pre-push.sh or prompts/ — Step 5 references
# examples/pre-push.sh, and the runner is the only way to produce the marker.
# Pi / gentle-ai is INTENTIONALLY omitted — Pi has its own 4R/JD/lens review
# pipeline which is strictly better than what this skill offers in Step 3.
#
# ~/.agents/skills is the canonical location: opencode scans it as an "external
# skill" root and picks up ~/.claude/skills at the same time, so a single link
# under ~/.agents/skills serves opencode, agy and gemini without duplicates.
# Borrado recuperable: la linea roja del repo prohibe borrar datos con `rm -rf`.
# `gio trash` deja el destino en la papelera en vez de destruirlo.
for dest in \
  "$HOME/.agents/skills/pre-push-qa" \
  "$HOME/.claude/skills/pre-push-qa" \
  "$HOME/.codex/skills/pre-push-qa" \
  "$HOME/.gemini/skills/pre-push-qa"; do
  mkdir -p "$(dirname "$dest")"
  if [ -e "$dest" ] || [ -L "$dest" ]; then gio trash "$dest"; fi
  ln -s "$SRC" "$dest"
done

# Hermes profile: point at the same source so SKILL.md never drifts again
HERMES_DEST="$HOME/.hermes/profiles/codehak/skills/software-development/pre-push-qa"
mkdir -p "$(dirname "$HERMES_DEST")"
if [ -e "$HERMES_DEST" ] || [ -L "$HERMES_DEST" ]; then gio trash "$HERMES_DEST"; fi
ln -s "$SRC" "$HERMES_DEST"

# Link the runner to PATH for global terminal execution
mkdir -p "$HOME/.local/bin"
ln -sf "$HOME/Proyectos/agent-fleet/skills/pre-push-qa/scripts/run.sh" "$HOME/.local/bin/pre-push-qa"

# Install the pre-push hook ONCE globally (all repos inherit via core.hooksPath)
mkdir -p "$HOME/.githooks"
cp "$SRC/examples/pre-push.sh" "$HOME/.githooks/pre-push"
chmod +x "$HOME/.githooks/pre-push"
git config --global core.hooksPath "$HOME/.githooks"

echo "Linked. Each agent will now load pre-push-qa when triggered by commit/push intent."
```

**Verify after install:**
```bash
# Whole directory resolves (not just SKILL.md)
ls ~/.agents/skills/pre-push-qa/                       # SKILL.md examples/ prompts/ scripts/
ls ~/.agents/skills/pre-push-qa/scripts/run.sh         # exists — the runner is reachable
# Enforcement is live
git config --global --get core.hooksPath               # ~/.githooks
test -x "$(git rev-parse --git-path hooks)/pre-push" && echo "hook active"
agy -p "test that you can see the pre-push-qa skill by listing skills" 2>&1 | head -20  # agy confirms load
# Pi: intentionally NOT installed. Use pi's native 4r-review / JD agents instead.
```

## Pitfalls (do not skip these)

- **Do NOT call `pnpm test --run`** — memory confirms pnpm 12+ rejects the `--run`
  flag. Always use `pnpm test -- --run` (the double-dash passes the flag through).
- **Do NOT pass `--if-present` to `tsc`** — it belongs to the script runner
  (`pnpm run`, `npm run`), not to the compiler. `tsc` exits 1 with `Unknown
  compiler option '--if-present'`, which fails the gate on every TypeScript
  repo. Guard the typecheck on `tsconfig.json` existing and on `typescript`
  being installed instead.
- **Do NOT pipe a test command without `set -o pipefail`** — `cmd | tail -40`
  returns the exit code of `tail`, so a failing suite looks green. The runner
  sets `pipefail`; ad-hoc commands outside it do not.
- **Do NOT treat a missing tool as a failed check** — `uv run <tool>` answers
  `Failed to spawn` (exit 2) when the tool is not in the project environment
  and not on the PATH. That is a missing tool, not a broken one. Probe first,
  then skip.
- **Do NOT run `npm ci` in repos with a `pnpm-lock.yaml`** — lockfile dictates the
  package manager. Use pnpm.
- **Do NOT install with `--frozen-lockfile` if the lockfile is stale** — `uv sync --frozen`
  fails on hash mismatches. Fall back to bare `uv sync` only as a last resort and report it.
- **Do NOT skip Step 2 because it "looks fine"** — `git diff --stat` showing "10 lines
  changed" is NOT the same as tests passing. Run them.
- **Do NOT auto-fix files outside `src/`, `tests/`, `app/`, `packages/`, `lib/`** — config
  changes need human review.
- **Do NOT push if `git status --porcelain` shows untracked files** that the user didn't
  mention — could be secrets, large binaries, etc.
- **Do NOT bypass git hooks that exist** — if the repo has husky/lefthook/pre-commit
  configured, those win. This skill augments; it doesn't replace.
- **Do NOT post the AI review to the PR without user approval** — a draft PR review
  in chat is fine; posting it to GitHub creates noise.
- **A failing gate is a FINDING, not a bug** — when the user's repo has pre-existing
  test failures (per memory, `optimacx-reclamos` has 17% failing), they must not
  block the push. The **baseline file** is what makes that possible: it lists the
  tests already known to fail, and only failures *outside* that list block. The
  runner reports `baseline-failures exist; new failures: <list>`.
  Generate it with `run.sh --update-baseline` and commit it: it is the list of
  failures the project decides to tolerate, so it has to be visible in the PR
  that adds it. If the runner cannot identify which tests failed, it blocks:
  the gate never gets weaker because it did not understand the output.
- **Lockfile mismatch after migration (Ubuntu→Arch, etc.)** — if `pnpm install` fails
  with `Cannot find module 'eslint/.../formatters/stylish'`, the right move is the
  bypass: `CI=1 pnpm install --config.confirmModulesPurge=false`. Don't try `npm install`.
- **Never track `.env` files or private keys** — any staged `.env` file (except `.env.example`/`.env.sample`) will trigger GitHub Secret Scanning and block pushes remotely. Verify with `git ls-files | grep '\.env'`.
- **Do NOT rely on local unmocked environment variables** — tests that pass only because your local machine has a `.env` file with live API keys will FAIL in GitHub Actions CI where those secrets do not exist. Always mock external APIs or provide CI fallback values in tests.

## Verification before reporting

Before telling the user "QA passed", verify:

1. Each command in Step 2 exited with code 0 (or was skipped).
2. The output captured includes the test summary line (e.g. `25 passed`, `XYZ tests ran`).
3. No file under `.venv`, `node_modules`, `.next`, `dist`, `build` is in the diff (those
   are noise, not real changes).
4. If you ran Step 4 (auto-fix), `git log -1` shows the new commit and `git diff HEAD~1`
   touches exactly one file under the allowed scope.

## Enforcement: one global hook, not one per repo

`git config --global core.hooksPath ~/.githooks` makes a hook copied into a repo's
`.git/hooks/` **inert** — git never reads that directory when `core.hooksPath` is set. So
install once globally and let every repo inherit it, instead of copying into each repo
and silently never running:

```bash
mkdir -p ~/.githooks
cp "$SRC/examples/pre-push.sh" ~/.githooks/pre-push
chmod +x ~/.githooks/pre-push
git config --global core.hooksPath ~/.githooks
```

If your agent refuses to write global instruction files (`~/.claude/CLAUDE.md`,
`~/.codex/AGENTS.md` are read-only in some setups), the hook is your only enforcement —
which is exactly why it must be installed and verified.

## Verify with a real round-trip, not a file listing

```bash
~/.local/bin/pre-push-qa; echo "runner exit=$?"                                     # 0 + marker
bash ~/.githooks/pre-push origin HEAD:refs/heads/selftest < /dev/null; echo "hook=$?"  # 0
```

El round-trip completo (marcador valido, marcador obsoleto, sin marcador) vive en
`scripts/verify-hook.sh`, que forma parte de `scripts/verify.sh`.

## Files in this skill

- `SKILL.md` — this file (the self-contained agent-agnostic procedure with embedded review & auto-fix guidelines)
- `scripts/run.sh` — standalone bash runner for local terminal checks and security scans
- `examples/pre-push.sh` — optional git pre-push hook for hard enforcement
- `prompts/` — fuente de verdad de los prompts de review y auto-fix. Los usan la CI (`scripts/review-call.js`, `scripts/auto-fix-attempt.js`) y el agente en local (Steps 3 y 4).
