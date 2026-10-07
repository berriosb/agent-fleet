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

**Terminal usage:**
`pre-push-qa` can also be run globally from any terminal when symlinked to `~/.local/bin/pre-push-qa`:
```bash
mkdir -p ~/.local/bin
ln -sf /home/bastianberrios/Proyectos/agent-fleet/skills/pre-push-qa/scripts/run.sh ~/.local/bin/pre-push-qa
```
Running `pre-push-qa` in any terminal runs stack detection, linters, tests, security checks, and creates the verification marker.

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
# pnpm
[ -f pnpm-lock.yaml ]                        → STACK=pnpm
   INSTALL = 'pnpm install --frozen-lockfile'
   LINT = 'pnpm run lint --if-present'
   TYPECHECK = 'pnpm exec tsc --noEmit --if-present || true'
   TEST = 'CI=true pnpm test --if-present 2>&1 | tail -40'
   BUILD = 'pnpm run build --if-present'

# yarn (lint, test, build scripts guarded via package.json check)
[ -f yarn.lock ]                             → STACK=yarn
   INSTALL = 'yarn install --frozen-lockfile'
   LINT = 'yarn run lint (guarded: if "lint" in package.json)'
   TYPECHECK = 'yarn run tsc --noEmit 2>/dev/null || true'
   TEST = 'CI=true yarn test (guarded: if "test" in package.json) 2>&1 | tail -40'
   BUILD = 'yarn run build (guarded: if "build" in package.json)'

# bun (lint, build scripts guarded via package.json check)
[ -f bun.lockb ] || [ -f bun.lock ]          → STACK=bun
   INSTALL = 'bun install --frozen-lockfile'
   LINT = 'bun run lint (guarded: if "lint" in package.json)'
   TYPECHECK = 'bun run tsc --noEmit 2>/dev/null || true'
   TEST = 'CI=true bun test 2>&1 | tail -40'
   BUILD = 'bun run build (guarded: if "build" in package.json)'

# npm
[ -f package-lock.json ]                     → STACK=npm
   INSTALL = 'npm ci --ignore-scripts'
   LINT = 'npm run lint --if-present'
   TYPECHECK = 'npx tsc --noEmit --if-present || true'
   TEST = 'CI=true npm test --if-present 2>&1 | tail -40'
   BUILD = 'npm run build --if-present'

# Python (uv)
[ -f uv.lock ] || [ -f pyproject.toml ]    → STACK=python
   LINT = 'uv run ruff check . --output-format=concise || ruff check . --output-format=concise || true'
   TYPECHECK = 'uv run mypy . --ignore-missing-imports 2>/dev/null || mypy . --ignore-missing-imports 2>/dev/null || true'
   TEST = 'uv run pytest -q --tb=line 2>&1 | tail -40 || pytest -q --tb=line 2>&1 | tail -40'

# Python (pip)
[ -f requirements.txt ] || [ -f setup.py ] → STACK=pip
   LINT = 'ruff check . --output-format=concise || true'
   TYPECHECK = 'mypy . --ignore-missing-imports 2>/dev/null || true'
   TEST = 'pytest -q --tb=line 2>&1 | tail -40'

# Node fallback without lockfile
[ -f package.json ]                          → STACK=npm
   INSTALL = 'npm install --ignore-scripts'
   LINT = 'npm run lint --if-present'
   TYPECHECK = 'npx tsc --noEmit --if-present || true'
   TEST = 'CI=true npm test --if-present 2>&1 | tail -40'
   BUILD = 'npm run build --if-present'

# Terraform
[ -f "*.tf" ] || ls *.tf 2>/dev/null         → STACK=terraform
   LINT = 'terraform fmt -check -recursive || terraform validate'

# Docker
[ -f Dockerfile ] || [ -f docker-compose.yml ] || [ -f docker-compose.yaml ] → STACK=docker
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
    if command -v uv >/dev/null 2>&1; then
      uv sync --frozen 2>/dev/null || uv sync || STATUS=$?
      uv run ruff check . --output-format=concise || STATUS=$?
      uv run mypy . --ignore-missing-imports 2>/dev/null || STATUS=$?
      uv run pytest -q --tb=line 2>&1 | tail -40 || STATUS=$?
    else
      command -v ruff >/dev/null 2>&1 && ruff check . --output-format=concise || STATUS=$?
      command -v mypy >/dev/null 2>&1 && mypy . --ignore-missing-imports 2>/dev/null || STATUS=$?
      command -v pytest >/dev/null 2>&1 && pytest -q --tb=line 2>&1 | tail -40 || STATUS=$?
    fi
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
    CI=true pnpm test --if-present 2>&1 | tail -40 || STATUS=$?
    pnpm run build --if-present || STATUS=$?
    ;;
  yarn)
    if grep -q '"lint":' package.json 2>/dev/null; then yarn run lint || STATUS=$?; fi
    yarn run tsc --noEmit 2>/dev/null || STATUS=$?
    if grep -q '"test":' package.json 2>/dev/null; then CI=true yarn test 2>&1 | tail -40 || STATUS=$?; fi
    if grep -q '"build":' package.json 2>/dev/null; then yarn run build || STATUS=$?; fi
    ;;
  bun)
    if grep -q '"lint":' package.json 2>/dev/null; then bun run lint || STATUS=$?; fi
    bun run tsc --noEmit 2>/dev/null || STATUS=$?
    CI=true bun test 2>&1 | tail -40 || STATUS=$?
    if grep -q '"build":' package.json 2>/dev/null; then bun run build || STATUS=$?; fi
    ;;
  npm)
    npm ci --ignore-scripts 2>/dev/null || npm install --ignore-scripts 2>/dev/null || STATUS=$?
    npm run lint --if-present || STATUS=$?
    npx tsc --noEmit --if-present 2>/dev/null || STATUS=$?
    CI=true npm test --if-present 2>&1 | tail -40 || STATUS=$?
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

**For Yarn and Bun**, `lint` and `test` scripts are safely guarded by inspecting `package.json` to prevent failures when a project does not define them.

**For pnpm specifically, MEMORY tells you `pnpm test --run` is rejected** — use the
double-dash form `pnpm test -- --run` or `pnpm vitest run`. This skill's commands above
follow that constraint.

## Step 3 — Optional: AI review (LLM-agnostic)

This step is **only run if the user hasn't disabled it**. The agent running this skill performs the review directly using its native reasoning (no external API keys or external script paths required):

1. Get the diff: `git diff HEAD` (or `git diff --cached` if changes are staged).
2. Adhere to this **Review System Prompt**:
   > **Role:** You are a senior code reviewer reviewing a pull request diff.
   > **Conventions:**
   > - Read `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` if present in the repo (they encode house style).
   > - Prefer findings that map to specific files and lines.
   > - Skip findings about pure formatting, comments, or import order unless they violate stated style.
   > - For ambiguous correctness questions, ask a question as a comment instead of asserting.
   >
   > **Output format — respond with ONE Markdown block:**
   > ```markdown
   > ## Code review
   > For each finding, output:
   > > **<severity>** — `<file>:<line>` — <one-sentence issue> — suggested fix: <one line>
   >
   > Severities: critical (correctness/security), high (will break), med (smell, future bug), low (nit).
   >
   > End with one of:
   > - LGTM (no findings)
   > - Approve with suggestions (≤ 3 findings, all low/med)
   > - Request changes (any critical or high)
   > ```
   > *Do NOT execute commands. Do NOT modify files. Output only the review.*

3. Post findings as comments in conversation. Do NOT modify code from the review step (auto-fix is a separate step, gated on user approval).

If the running environment lacks an interactive LLM agent → skip Step 3 entirely. The static + tests in Step 2 are the load-bearing part.

## Step 4 — Optional: Auto-fix attempts (HITL by default)

**Never auto-fix without explicit user permission.** When lint or tests fail:

1. Extract the FIRST error from the failing log (≤ 100 lines).
2. Adhere to this **Surgical Fix Specification**:
   > **Hard rules (NO exceptions):**
   > 1. Modify AT MOST ONE file under allowed paths: `src/`, `tests/`, `app/`, `packages/`, `lib/`.
   > 2. The fix must be a mechanical, deterministic change (typo, missing import, wrong attribute name, off-by-one in a fixture, syntax error). If the failure requires redesign → **ABORT** and report failure to user.
   > 3. Do NOT touch configs, lockfiles, or CI files.
   > 4. Do NOT add new external dependencies.
   > 5. Do NOT refactor or rename variables unnecessarily.
   > 6. Replacement MUST be an exact contiguous block match.
   > 7. Verify syntax/tests before committing. Commit ONLY that file under author's own identity (Zero AI Branding).
3. If the proposal is mechanical and safe, propose it to the user. Upon confirmation, apply and commit ONLY that file.
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
     `git ls-files | grep -E '(^|/)\.env(\.[^/]+)?$' | grep -vE '\.env\.(example|sample|template|test|ci|defaults)$'`
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
for dest in \
  "$HOME/.agents/skills/pre-push-qa" \
  "$HOME/.claude/skills/pre-push-qa" \
  "$HOME/.codex/skills/pre-push-qa" \
  "$HOME/.gemini/skills/pre-push-qa"; do
  rm -rf "$dest"
  mkdir -p "$(dirname "$dest")"
  ln -s "$SRC" "$dest"
done

# Hermes profile: point at the same source so SKILL.md never drifts again
rm -rf "$HOME/.hermes/profiles/codehak/skills/software-development/pre-push-qa"
ln -s "$SRC" "$HOME/.hermes/profiles/codehak/skills/software-development/pre-push-qa"

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
rm -f "$(git rev-parse --git-dir)/pre-push-qa-ok"
~/.local/bin/pre-push-qa; echo "runner exit=$?"                                     # 0 + marker
bash ~/.githooks/pre-push origin HEAD:refs/heads/selftest < /dev/null; echo "hook=$?"  # 0
rm -f "$(git rev-parse --git-dir)/pre-push-qa-ok"                                   # always clean up
```

## Files in this skill

- `SKILL.md` — this file (the self-contained agent-agnostic procedure with embedded review & auto-fix guidelines)
- `scripts/run.sh` — standalone bash runner for local terminal checks and security scans
- `examples/pre-push.sh` — optional git pre-push hook for hard enforcement
- `prompts/` — reference copies of review and auto-fix prompts
