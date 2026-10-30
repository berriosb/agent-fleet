---
name: fleet-story
description: "Takes ONE user story from the backlog and adds 2-3 acceptance criteria, a mini plan and an explicit out of scope. Trigger: there IS a story and what it has to satisfy is still undefined. NOT creating the backlog (fleet-backlog), NOT deciding the design (fleet-interview), NOT implementing (fleet-pair)."
version: 1.0.0
license: MIT
disable-model-invocation: true
metadata:
  author: nschurmann/hola-ai
  upstream: https://github.com/nschurmann/hola-ai/tree/main/skills/story
---

# fleet-story

## En la cadena

Fase 1 — Diseño. Explícita: se invoca con una historia concreta del backlog que
`fleet-backlog` produjo. Su salida es la entrada de `fleet-pair`.
Orden completo: [`CHAIN.md`](../fleet-conventions/CHAIN.md).

We refine a single story, right before building it. You propose and I decide.

## Steps

1. **Read the story** I give you (pasted text, GitHub issue, Jira ticket, etc.) and
   review the current code and `AGENTS.md` to understand the context.
2. **Acceptance criteria.** Propose 2-3 in Given/When/Then format. They only
   describe *what* the user sees or gets, never *how* it's implemented.
3. **If it needs more than 3 criteria, don't bloat it: propose splitting it.**
   Deliver the new stories in backlog format (`As a..., I want..., so that...`) for
   me to add to the tracker, and we continue with the first one.
4. **Mini plan.** 5 bullets max, no code or file names. How it cuts through the
   layers, with the minimum that meets the criteria.
5. **Wait for my approval.** We adjust until I say yes.

## Rules

- **Don't invent requirements.** If information is missing, ask me.
- **The simplest thing that meets the criteria.** No abstractions, layers,
  configuration or patterns "for the future".
- **Suggest, don't decide.** If a pattern could help (Atomic Design, middleware
  composition, extracting a component...), mention it under "Suggestions" with its
  why. Only suggest it if there's a concrete signal in the code (for example,
  something that already repeats), not in advance.
- **Don't write code.**
- **Out of scope is not optional.** A story without an explicit out-of-scope list
  grows during the implementation, every time.

## Output format

A block ready to paste into the issue. `fleet-pair` uses it as input.

```markdown
## Story
As a <actor>, I want <action>, so that <benefit>.

## Acceptance criteria
- [ ] Given <context>, when <action>, then <result>.
- [ ] ...

## Plan
- ...

## Out of scope
- <what's left out of this story, so it doesn't sneak in>

## Suggestions (your call)
- <optional>
```
