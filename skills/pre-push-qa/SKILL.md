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
    related: [requesting-code-review, github, multi-repo-portfolio-audit]
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

**Relationship to other skills:**
- `requesting-code-review` (you already have): local pre-commit security + reviewer subagent.
  Heavy, requires a fresh subagent. **Use this skill when you want lighter, faster, no-LLM pass.**
- `github`: PR/branch/CI lifecycle; assumes a remote exists. This skill runs **before** that.
- `multi-repo-portfolio-audit`: portfolio-wide lint/TODO sweeps. This skill is single-repo.
- CI/remote: each repository runs its own standard CI checks. This skill acts strictly *before* push.

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

## Step 1 — Auto-detect the stack and the right commands

Read these project files IN ORDER to pick commands (first match wins):

```bash
# Python (uv)
[ -f uv.lock ] || [ -f pyproject.toml ]    → STACK=python
   LINT = 'uv run ruff check . --output-format=concise || true'
   TYPECHECK = 'uv run mypy . --ignore-missing-imports || true'
   TEST = 'uv run pytest -q --tb=line 2>&1 | tail -40'

# Python (pip)
[ -f requirements.txt ] || [ -f setup.py ] → STACK=pip
   LINT = 'ruff check . --output-format=concise || true'
   TYPECHECK = 'mypy . --ignore-missing-imports || true'
   TEST = 'pytest -q --tb=line 2>&1 | tail -40'

# pnpm
[ -f pnpm-lock.yaml ]                        → STACK=pnpm
   INSTALL = 'pnpm install --frozen-lockfile'
   LINT = 'pnpm run lint --if-present'
   TYPECHECK = 'pnpm exec tsc --noEmit --if-present || true'
   TEST = 'pnpm test -- --run --reporter=default 2>&1 | tail -40'
   BUILD = 'pnpm run build --if-present'

# npm
[ -f package-lock.json ]                     → STACK=npm
   INSTALL = 'npm ci --ignore-scripts'
   LINT = 'npm run lint --if-present'
   TYPECHECK = 'npx tsc --noEmit --if-present || true'
   TEST = 'npm test -- --passWithNoTests 2>&1 | tail -40'
   BUILD = 'npm run build --if-present'

# Terraform
[ -f "*.tf" ] || ls *.tf 2>/dev/null         → STACK=terraform
   LINT = 'terraform fmt -check -recursive || terraform validate'

# Docker
[ -f Dockerfile ] || [ -f docker-compose.yml ] → STACK=docker
   LINT = 'hadolint Dockerfile || true'

# Docs-only (ONLY when repository has zero code files: no .py, .ts, .js, .go, .rs, .tf, .sh, etc.)
# If the repository contains code files or manifests, NEVER classify as docs-only.
no code files && find . -maxdepth 3 -name "*.md" → STACK=docs
   # Nothing to lint/test; verify markdown with 'markdownlint --if-present'
```

If none match: STACK=mixed — run whatever matches, ignore missing steps.

**Always skip lint/test if the diff only touches:** `*.md`, `*.mdx`, `docs/**`,
`.github/ISSUE_TEMPLATE/**`, `assets/**`, `*.lock` (unless manifest-affecting),
`*.svg`, `*.png`.

## Step 2 — Run static + tests (the cheap, fast, free part)

Run sequentially in a single subshell so you capture all output:

```bash
STATUS=0
case "$STACK" in
  python)
    uv sync --frozen 2>/dev/null || uv sync || STATUS=$?
    uv run ruff check . --output-format=concise || STATUS=$?
    uv run mypy . --ignore-missing-imports 2>/dev/null || STATUS=$?
    uv run pytest -q --tb=line 2>&1 | tail -40 || STATUS=$?
    ;;
  pip)
    ruff check . --output-format=concise 2>/dev/null || STATUS=$?
    mypy . --ignore-missing-imports 2>/dev/null || STATUS=$?
    pytest -q --tb=line 2>&1 | tail -40 || STATUS=$?
    ;;
  pnpm)
    pnpm install --frozen-lockfile --ignore-scripts 2>/dev/null || STATUS=$?
    pnpm run lint --if-present || STATUS=$?
    pnpm exec tsc --noEmit --if-present 2>/dev/null || STATUS=$?
    pnpm test -- --run 2>&1 | tail -40 || STATUS=$?
    pnpm run build --if-present || STATUS=$?
    ;;
  npm)
    npm ci --ignore-scripts 2>/dev/null || STATUS=$?
    npm run lint --if-present || STATUS=$?
    npx tsc --noEmit --if-present 2>/dev/null || STATUS=$?
    npm test -- --passWithNoTests 2>&1 | tail -40 || STATUS=$?
    npm run build --if-present || STATUS=$?
    ;;
  terraform)
    terraform fmt -check -recursive || STATUS=$?
    ;;
  docker)
    hadolint Dockerfile 2>/dev/null || STATUS=$?
    ;;
  docs) echo "docs-only — skipping lint/tests";;
  *)   echo "unknown stack — running best-effort";;
esac
exit $STATUS
```

**If something fails here: STOP and fix it before going to Step 3.** Most CI failures
come from lint or import errors that this step catches.

**For pnpm specifically, MEMORY tells you `pnpm test --run` is rejected** — use the
double-dash form `pnpm test -- --run` or `pnpm vitest run`. This skill's commands above
follow that constraint.

## Step 3 — Optional: AI review (LLM-agnostic)

This step is **only run if the user hasn't disabled it**. The agent running this skill
should:

1. Get the diff: `git diff HEAD` (or `git diff --cached` if everything is staged).
2. Call **whatever LLM the agent has access to** (Claude, M3, Gemini, GPT-4, etc.).
3. Use `prompts/review.md` as the system prompt.
4. Post findings as comments. Do NOT modify code from the review step (auto-fix is a
   separate step, gated on user approval).

If the running agent lacks a usable LLM call → skip Step 3 entirely. The static + tests
in Step 2 are the load-bearing part.

## Step 4 — Optional: Auto-fix attempts (HITL by default)

**Never auto-fix without explicit user permission.** When lint or tests fail:

1. Extract the FIRST error from the failing log (≤ 100 lines).
2. Try ONE proposed change with `prompts/auto-fix.md` as the prompt.
3. If the proposal is mechanical and within `src/`, `tests/`, `app/`, `packages/`, `lib/`,
   commit ONLY that file.
4. Otherwise, surface the failure to the user and stop.

If the user said "just push it / don't stop on CI failures", skip Step 4 entirely.

## Step 5 — Push guard & Verification Marker

Before pushing, the agent must verify and execute:

1. **Confirm checks passed:**
   - [ ] `git status --porcelain` is clean OR the only changes are the auto-fix from Step 4
   - [ ] All lint commands in Step 2 exited 0
   - [ ] All typecheck commands in Step 2 exited 0
   - [ ] All test commands in Step 2 exited 0
   - [ ] Build check passed (`build --if-present` exited 0)
   - [ ] No `.env` or private keys tracked in git (`git ls-files | grep '\.env'`)
   - [ ] CI Secret Independence: Tests do NOT depend on unmocked local-only environment variables missing from CI
   - [ ] User has approved the commit message (or agreed to auto-generated `[skip ci]` prefix)

2. **Generate the Git Hook Verification Marker:**
   If the local environment uses the pre-push hook (`examples/pre-push.sh`), it requires a valid marker matching the current HEAD commit.
   Create the marker before running `git push`:
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
| **OpenCode** | Symlink into `~/.config/opencode/skills/pre-push-qa/`. OpenCode loads skills from that path. |
| **Codex CLI** | Drop into `~/.codex/skills/pre-push-qa/`. Codex picks up skills per `~/.codex/skills/`. |
| **Gemini CLI** | Symlink into `~/.gemini/skills/pre-push-qa/`. Gemini CLI auto-discovers. |
| **Antigravity CLI (`agy`)** | `agy` is a Google CLI, **not** based on VS Code (the `extensions/` dir holds LSP language servers only). Skills live at `~/.agents/skills/<name>/SKILL.md` (same path as gemini-cli). To install: `mkdir -p ~/.agents/skills/pre-push-qa && ln -sf $HOME/.hermes/profiles/codehak/skills/software-development/pre-push-qa/SKILL.md ~/.agents/skills/pre-push-qa/SKILL.md`. Confirm with `agy plugin list` and a quick prompt mentioning "commit". |
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
npx skills add berriosb/pre-push-qa -g
```

### Option 2: Manual symlink / clone
```bash
SRC="$HOME/Proyectos/pre-push-qa/skills/pre-push-qa"
# Or if using Hermes profile:
# SRC="$HOME/.hermes/profiles/codehak/skills/software-development/pre-push-qa"

# Mirror the skill into each agent's skill path.
# Pi / gentle-ai is INTENTIONALLY omitted — Pi has its own 4R/JD/lens review
# pipeline which is strictly better than what this skill offers in Step 3.
for dest in \
  "$HOME/.claude/skills/pre-push-qa" \
  "$HOME/.config/opencode/skills/pre-push-qa" \
  "$HOME/.codex/skills/pre-push-qa" \
  "$HOME/.gemini/skills/pre-push-qa" \
  "$HOME/.agents/skills/pre-push-qa"; do
    mkdir -p "$dest"
    ln -sf "$SRC/SKILL.md" "$dest/SKILL.md"
done

echo "Linked. Each agent will now load pre-push-qa when triggered by commit/push intent."
```

**Verify after install:**
```bash
ls -la ~/.claude/skills/pre-push-qa/SKILL.md       # symlink OK
ls -la ~/.agents/skills/pre-push-qa/SKILL.md       # symlink OK (agy AND gemini share this path)
agy -p "test that you can see the pre-push-qa skill by listing skills" 2>&1 | head -20  # agy confirms load
# Pi: intentionally NOT installed. Use pi's native 4r-review / JD agents instead.
```

## Pitfalls (do not skip these)

- **Do NOT call `pnpm test --run`** — memory confirms pnpm 12+ rejects the `--run`
  flag. Always use `pnpm test -- --run` (the double-dash passes the flag through).
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
  test failures (per memory, `optimacx-reclamos` has 17% failing), report them as
  "baseline-failures exist; new failures: <list>" rather than blocking.
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

## Files in this skill

- `SKILL.md` — this file (the agent-agnostic procedure)
- (no scripts — agents run the commands inline; no API keys required)

## Related tools in this repository

- `scripts/run.sh` — standalone bash script to run the same stack detection and tests locally.
- `examples/pre-push.sh` — optional git pre-push hook to enforce checks before `git push`.
