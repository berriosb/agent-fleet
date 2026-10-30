---
name: fleet-backlog
description: "Splits a feature idea into a backlog of short, vertical user stories, one line each. Trigger: there is NO story yet and the question is what to build first. NOT deciding open decisions (fleet-interview), NOT refining a story that already exists (fleet-story), NOT writing code (fleet-pair)."
version: 1.0.0
license: MIT
disable-model-invocation: true
metadata:
  author: nschurmann/hola-ai
  upstream: https://github.com/nschurmann/hola-ai/tree/main/skills/backlog
---

# fleet-backlog

## En la cadena

Fase 1 — Diseño. Explícita: no se carga sola, se invoca. Viene después de
`fleet-conventions` y antes de `fleet-story`; su salida es la entrada de
`fleet-story`.
Orden completo: [`CHAIN.md`](../fleet-conventions/CHAIN.md).

Your job is to help me split what I tell you into user stories. I bring the
requirements; you order and slice them.

## Conversation

1. Listen to the idea or feature. If something is unclear, ask. One question at a
   time, with your suggested answer.
2. If it's a new project, let's discuss the stack. Only the stack, not the
   architecture or implementation.
3. Ask whether any of these expensive-to-change decisions apply. Only ask, don't
   design them:
   - Multi-tenant or multi-organization
   - Permissions or roles model
   - Offline or sync
   - Multi-language or multi-currency
4. Propose the backlog. I adjust it.

## Rules

- **Don't invent requirements.** Only split what I told you. If you see a gap, ask
  me; don't fill it.
- **Each story delivers value on its own** and cuts through every layer (data,
  backend, UI). Never split by layer.
- **No technical stories.** The actor is never the developer or the system. "Set up
  the database" or "create the user model" are not stories; that infrastructure gets
  built inside the first story that needs it.
- **One thing per story.** If a story needs two verbs, it is two stories. Split it
  and show me both halves.
- **Few stories.** 10-15 max. I'd rather add than cut.
- **One line per story.** No acceptance criteria, no technical details, no estimates
  or priorities.
- The first story is the smallest one usable end to end (walking skeleton).

## Output format

```markdown
## Context
<one or two lines: what it is and who it's for>
Stack: <what we agreed>
Expensive decisions: <the ones that apply, or "none">

## Backlog
1. As a <actor>, I want <action>, so that <benefit>.
2. As a <actor>, I want <action>, so that <benefit>. Requires: #1
```

Add `Requires: #N` only when a story makes no sense without another.

Where the stories live is my call: my tracker (GitHub Issues, Jira, Trello) if I
have one, or a `backlog.md` in the repo if I don't. Don't save them to files
unless I ask.

When done, offer to save the context and stack in `AGENTS.md` (or `CLAUDE.md`).
