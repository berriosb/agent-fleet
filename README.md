# pre-push-qa

Agent-agnostic pre-push quality gate. Runs lint, tests, and a push-guard in any of your
agents (Codex, OpenCode, Antigravity `agy`, Gemini CLI, Claude Code, or terminal) before
a `git push`. Optional AI review via MiniMax M3 (no new API key — uses your existing
subscription).

The reusable workflow in `.github/workflows/qa.yml` is the CI-side companion: it picks up
the slack if a push bypassed the local skill, and adds an `auto-fix` side-branch when
lint/tests fail.

## What's in this repo

| Path | What |
|---|---|
| `skills/pre-push-qa/SKILL.md` | The agent skill. Symlink it into each agent's skill path. |
| `.github/workflows/qa.yml` | **Reusable workflow.** Consumer repos import this via `uses: berriosb/pre-push-qa/.github/workflows/qa.yml@v1`. |
| `prompts/review.md` | AI review system prompt (MiniMax M3-tuned; works with any OpenAI-compatible LLM). |
| `prompts/auto-fix.md` | Auto-fix prompt. Strict: one file, one mechanical change. |
| `scripts/review-call.js` | Calls MiniMax M3 `/chat/completions` and writes the review comment to a file. |
| `scripts/auto-fix-attempt.js` | Opens a side-branch with a mechanical fix attempt, guarded by HITL. |
| `examples/pre-push.sh` | **Optional** git `pre-push` hook for users who want hard enforcement. Off by default. |

## Install the skill on each agent (5 symlinks, 30 seconds)

```bash
SRC="$HOME/.hermes/profiles/codehak/skills/software-development/pre-push-qa"
for dest in \
  "$HOME/.claude/skills/pre-push-qa" \
  "$HOME/.config/opencode/skills/pre-push-qa" \
  "$HOME/.codex/skills/pre-push-qa" \
  "$HOME/.gemini/skills/pre-push-qa" \
  "$HOME/.agents/skills/pre-push-qa"; do
    mkdir -p "$dest"
    ln -sf "$SRC/SKILL.md" "$dest/SKILL.md"
done
```

> **Pi / gentle-ai is intentionally excluded** — it has 4R / JD / lens review which is
> strictly stronger than this skill's review step.

Verify:
```bash
ls -la ~/.claude/skills/pre-push-qa/SKILL.md
ls -la ~/.agents/skills/pre-push-qa/SKILL.md
agy -p "list the available skills" 2>&1 | head -10
```

## Enable the CI gate on a consumer repo (60 seconds)

Copy `.github/workflows/gatling.yml` from the README section below into your repo's
`.github/workflows/` directory and set `MINIMAX_API_KEY` + `MINIMAX_BASE_URL` as repo
secrets:

```bash
gh secret set MINIMAX_API_KEY   --body "$MINIMAX_API_KEY"
gh secret set MINIMAX_BASE_URL  --body "$MINIMAX_BASE_URL"
```

The `gatling.yml` consumer file (paste this into `.github/workflows/gatling.yml` in
each consumer repo):

```yaml
name: gatling
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
concurrency:
  group: gatling-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true
permissions:
  contents: read
  pull-requests: write
  issues: write
  checks: write
jobs:
  qa:
    uses: berriosb/pre-push-qa/.github/workflows/qa.yml@v1
    with:
      stack: auto
      enable_ai_review: true
      enable_auto_fix: true
      llm_provider: minimax
      skip_if_coderabbit: true
      draft_pr: ${{ github.event.pull_request.draft }}
    secrets:
      MINIMAX_API_KEY: ${{ secrets.MINIMAX_API_KEY }}
      MINIMAX_BASE_URL: ${{ secrets.MINIMAX_BASE_URL }}
```

## Coexistence with CodeRabbit

The reusable workflow checks for a recent CodeRabbit review and skips the AI review pass
to save tokens. Configurable via `skip_if_coderabbit: true` (default).

## What this skill does NOT do

- **No git hook by default.** It's a skill that the agent loads. Trigger is agent
  initiative, not `git push`. If you want hard enforcement, see
  [`examples/pre-push.sh`](examples/pre-push.sh).
- **No AI model review in Pi / gentle-ai.** Pi has better review machinery.
- **No force-push / --no-verify enforcement.** Use a separate hook for that (the
  community [`block-no-verify-hook`](https://www.skills.sh/wshobson/agents/block-no-verify-hook)
  is recommended as a complement).
- **No secret scanning in the skill itself.** Recommended:
  [`push-gate`](https://www.skills.sh/0xdarkmatter/claude-mods/push-gate) as a
  complementary check for secrets via Gitleaks.

## Roadmap (post-private)

- [ ] Add baseline-aware test failure handling (skip if a previously-failing test was
      already failing before the diff)
- [ ] Switch AI review to Anthropic Claude as opt-in fallback
- [ ] Add Gemini 3 Flash for docs-only PRs as a cheaper check
- [ ] Promote to public once we have CI failure-rate metrics from 5+ repos
