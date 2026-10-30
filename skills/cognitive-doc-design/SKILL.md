---
name: cognitive-doc-design
description: "Designs the content of a doc, README, ADR or PR body so a reviewer can verify it without reconstructing the story. Trigger: writing documentation. NOT the domain vocabulary (domain-modeling) and NOT running the checks (pre-push-qa)."
license: Apache-2.0
version: 1.0.0
metadata:
  author: gentleman-programming
---

## En la cadena

Fase 2 — Implementación: cada doc, README o nota de arquitectura que escribís.
Fase 5 — Push: el cuerpo del PR.
Orden completo: [`CHAIN.md`](../fleet-conventions/CHAIN.md).

## When to Use

Load this skill when creating or editing documentation that people need to understand quickly, retain, or use during review.

Use it especially for:

- PR descriptions and review notes.
- Contributor or maintainer guides.
- Architecture, workflow, or onboarding docs.
- Any doc that currently feels long, dense, or hard to scan.

## Critical Patterns

| Pattern | Rule |
|---------|------|
| Lead with the answer | Put the decision, action, or outcome first. Context comes after. |
| Progressive disclosure | Start with the happy path, then add details, edge cases, and references. |
| Chunking | Group related information into small sections. Keep flat lists short. |
| Signposting | Use headings, labels, callouts, and summaries so readers know where they are. |
| Recognition over recall | Prefer tables, checklists, examples, and templates over prose that must be remembered. |
| Review empathy | Design docs so reviewers can verify intent without reconstructing the whole story. |

## Documentation Shape

Use this default structure unless the repo already provides a stronger template:

```markdown
# <Outcome-oriented title>

<One paragraph: what changed, who it helps, and why it matters.>

## Quick path

1. <First action>
2. <Second action>
3. <Verification or expected result>

## Details

| Topic | Decision |
|-------|----------|
| <area> | <concise explanation> |

## Checklist

- [ ] <Reader can confirm this>
- [ ] <Reader can confirm that>

## Next step

<Link or action that continues the workflow.>
```

## PR and Review Docs

A PR body has **one canonical shape**. Use it whenever you write a PR description, a
review note, or a changelog entry that stands in for one:

```markdown
## Summary
[1-2 sentences: what problem is solved and why]

## Changes
- [Concise bullet of change 1]
- [Concise bullet of change 2]

## Verification
- [command]: [exact result]

## Out of scope
- [what this PR does NOT do, so the reviewer doesn't look for it]

## Review path
- Start here: [file:line]
- [ ] [criterion the reviewer can confirm]
```

The sections are ordered by what the reviewer needs first: what it is, what changed,
how it was proven, what it does not cover, and where to look. A section that has
nothing to say is omitted — except `Verification`, which never is.

When documenting a PR, reduce reviewer burnout by making the review path explicit:

- State what to review first, with a file and a line.
- State what is intentionally out of scope.
- Link the previous and next PR when work is chained.
- Keep each section focused on one decision or unit of work.
- Use checklists for acceptance criteria and verification.

This shape is the canonical one for the whole fleet. `pre-push-qa` uses it too, and
`scripts/check-skills.py` verifies that the two do not drift apart.

## Commands

```bash
# Check markdown files changed in the current branch
git diff --name-only -- '*.md'

# Inspect PR changed-line count for cognitive load
gh pr view <PR_NUMBER> --json additions,deletions,changedFiles
```
