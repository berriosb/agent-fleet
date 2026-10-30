---
name: work-unit-commits
description: "Decides what goes in each commit, how to split a change into reviewable work units, and with what message. Trigger: planning commits, splitting a large PR into chained ones, or defining the rollback boundary. NOT writing the code (fleet-pair) and NOT running the checks (pre-push-qa)."
license: Apache-2.0
version: 1.0.0
metadata:
  author: gentleman-programming
---

## En la cadena

Fase 1 — Diseño: para partir el trabajo en commits antes de implementar.
Fase 4 — Commit: antes de cada `git commit`, para decidir qué va en este commit.
Orden completo: [`CHAIN.md`](../fleet-conventions/CHAIN.md).

## When to Use

Load this skill when deciding what belongs in each commit or PR.

Use it for:

- Splitting a feature into reviewable work.
- Preparing commits before opening a PR.
- Turning a large change into chained or stacked PRs.
- Keeping reviewer cognitive load healthy.
- Applying SDD tasks without accidentally producing a PR above 400 changed lines.

## Critical Rules

| Rule | Requirement |
|------|-------------|
| Commit by work unit | A commit represents a deliverable behavior, fix, migration, or docs unit. |
| Do not commit by file type | Avoid `models`, then `services`, then `tests` if none works alone. |
| Keep tests with code | Tests belong in the same commit as the behavior they verify. |
| Test with the code | **The test changes in the same commit as the implementation.** Read the test's diff first: a test that changed after the code was green is tampering, not refactoring. |
| Keep docs with the user-visible change | Docs belong with the feature or workflow they explain. |
| Tell a story | A reviewer should understand why each commit exists from its diff and message. |
| Future PR-ready | Each commit should be a candidate chained PR when the change grows. |
| Large-change guard | If the change forecasts more than 400 changed lines, group commits into chained PR slices before implementation. |

## Work Unit Checklist

Before committing, confirm:

- [ ] The commit has one clear purpose.
- [ ] The repo still makes sense after applying only this commit.
- [ ] Tests or docs for this unit are included when relevant.
- [ ] The test file changed before the implementation did, and no test changed after the code was already green.
- [ ] Rollback is reasonable without reverting unrelated work.
- [ ] Focused test command and exact result are recorded.
- [ ] Runtime harness command/scenario and exact result are recorded, or explicit `N/A` explains why no runtime boundary exists.
- [ ] Rollback boundary names the exact files/behavior removable without unrelated work.
- [ ] The commit message explains the outcome, not the file list.

## The test's diff comes first

The test belongs in the same commit as the behavior it verifies, and
**the test changes in the same commit as the implementation**. Git orders a diff
by path, not by intent: in a `src/` + `tests/` layout the source file is listed
first, and in a colocated layout it depends on the file names. So the order in
the diff is not a property you can rely on — the *review* is.

What makes the commit auditable is the reading order:

1. `git show <sha> -- <test file>` — what was written for the test.
2. `git show <sha> -- <implementation file>` — what was written for the code.

If the test changed after the implementation was already green, that is
tampering, not refactoring — and the red-green check in
`verification-before-completion` is what proves it: revert the fix, the test
must fail.

## Split Examples

| Weak split | Better work-unit split |
|------------|------------------------|
| `add models` | `feat(auth): add token validation domain model and tests` |
| `add services` | `feat(auth): wire token validation into login flow` |
| `add tests` | Tests included with each behavior commit |
| `update docs` | Docs included with the user-facing change they explain |

## PR Relationship

Use work-unit commits as the foundation for chained PRs:

1. Build the smallest independent work unit.
2. Include verification for that unit.
3. Commit it with a Conventional Commit message.
4. If the PR approaches 400 changed lines, promote commits or groups of commits into chained PRs.

## Evidence and Thresholds

Every work unit closes with:

- a clear start state,
- a clear finished state,
- verification inside the same unit,
- a rollback that does not remove unrelated work.

The implementation evidence for a work unit MUST include:

- the focused test command and its exact result,
- the runtime harness command/scenario and its exact result, or an explicit `N/A` with the
  reason why no runtime boundary exists,
- the rollback boundary, stated independently of commit creation — uncommitted work units
  require it too.

Count **authored** additions plus deletions for the `>400` threshold: exclude generated
goldens from the authored count, but include every generated file in the snapshot identity
and receipt validation.

When a change forecasts more than 400 changed lines, group the commits into chained PR
slices before implementing, not after.

## Commands

```bash
# Review the story before committing
git diff --stat
git diff --cached --stat

# Check recent commit style
git log --oneline -5
```
