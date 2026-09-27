# pre-push-qa

Compuerta de calidad pre-push agnóstica al agente. Corre lint, tests y un push-guard en
cualquiera de tus agentes (Codex, OpenCode, Antigravity `agy`, Gemini CLI, Claude Code
o terminal) antes de un `git push`. Review por IA opcional contra cualquier endpoint
OpenAI-compatible (MiniMax M3, Anthropic, OpenAI, Gemini — el que tengas configurado).

El workflow reusable en `.github/workflows/qa.yml` es el complemento del lado de CI:
levanta la red de seguridad si un push se saltó la skill local, y abre una rama
`auto/fix-<run_id>` cuando lint o tests fallan.

## Qué hay en este repo

| Ruta | Qué es |
|---|---|
| `skills/pre-push-qa/SKILL.md` | La skill del agente. Symlink en el path de skills de cada agente. |
| `.github/workflows/qa.yml` | **Workflow reusable.** Los repos consumidores lo importan con `uses: berriosb/pre-push-qa/.github/workflows/qa.yml@v1`. |
| `prompts/review.md` | System prompt para review por IA. Agnóstico al LLM. |
| `prompts/auto-fix.md` | Prompt de auto-fix. Estricto: un archivo, un cambio mecánico. |
| `scripts/review-call.js` | Llama a un endpoint OpenAI-compatible `/chat/completions` y escribe el comentario de review. |
| `scripts/auto-fix-attempt.js` | Abre una rama side-branch con un intento de fix mecánico, con HITL. |
| `examples/pre-push.sh` | Hook git `pre-push` **opcional** para quien quiera enforcement duro. Apagado por defecto. |

## Instalar la skill en cada agente (5 symlinks, 30 segundos)

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

> **Pi / gentle-ai queda intencionalmente fuera** — ya tiene 4R / JD / lens review, que
> es estrictamente más fuerte que el paso de review de esta skill.

Verificar:
```bash
ls -la ~/.claude/skills/pre-push-qa/SKILL.md
ls -la ~/.agents/skills/pre-push-qa/SKILL.md
agy -p "list the available skills" 2>&1 | head -10
```

## ⚠️ Nota sobre `.github/workflows/qa.yml` y el run fallido que vas a ver

`qa.yml` declara `on: workflow_call`. Es un **workflow reusable** — solo corre cuando
otro repo lo invoca vía `uses: berriosb/pre-push-qa/.github/workflows/qa.yml@v1`.

Como `qa.yml` declara `workflow_call`, GitHub reporta un run fallido con
"No se ejecutaron trabajos" la primera vez que lo subís. **Esa falla es esperada**,
no es un bug. El workflow compañero `validate.yml` (en la misma carpeta) sí corre en
cada push a `main` y verifica que `qa.yml` sea sintácticamente válido usando
`gh workflow lint`.

Cuando después instales `gatling.yml` en un repo consumidor (ver la siguiente sección),
el push de ese consumidor va a disparar `qa.yml` de verdad — y va a correr los 4 jobs
(static / tests / ai-review / auto-fix) como corresponde.

## Activar el gate de CI en un repo consumidor (60 segundos)

Pegá este archivo en `.github/workflows/gatling.yml` del repo consumidor y configurá
`MINIMAX_API_KEY` + `MINIMAX_BASE_URL` como secrets del repo:

```bash
gh secret set MINIMAX_API_KEY   --body "$MINIMAX_API_KEY"
gh secret set MINIMAX_BASE_URL  --body "$MINIMAX_BASE_URL"
```

El archivo `gatling.yml` (pegá esto en `.github/workflows/gatling.yml` en cada repo
consumidor):

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
      draft_pr: ${{ github.event.pull_request.number && github.event.pull_request.draft }}
    secrets:
      MINIMAX_API_KEY: ${{ secrets.MINIMAX_API_KEY }}
      MINIMAX_BASE_URL: ${{ secrets.MINIMAX_BASE_URL }}
```

## Coexistencia con CodeRabbit

El workflow reusable detecta si CodeRabbit ya revisó el PR (buscando el patrón
`@coderabbit|CodeRabbit|coderabbitai` en los comentarios recientes) y se saltea el
review con IA para ahorrar tokens. Configurable con `skip_if_coderabbit: true` (default).

## Qué NO hace esta skill

- **No es git hook por defecto.** Es una skill que el agente carga. El trigger es la
  iniciativa del agente, no `git push`. Si querés enforcement duro, mirá
  [`examples/pre-push.sh`](examples/pre-push.sh).
- **No hace review por IA dentro de Pi / gentle-ai.** Pi tiene mejor maquinaria de
  review.
- **No enforce `git push --force` ni `--no-verify`.** Para eso, sumá el skill
  [`block-no-verify-hook`](https://www.skills.sh/wshobson/agents/block-no-verify-hook)
  de la comunidad como complemento.
- **No hace secret scanning.** Recomendado como complemento:
  [`push-gate`](https://www.skills.sh/0xdarkmatter/claude-mods/push-gate) que usa
  Gitleaks.

## Roadmap (post-privado)

- [ ] Manejo de tests baseline-aware (no romper si el test ya fallaba antes del diff)
- [ ] Switch del review por IA a Anthropic Claude como fallback opcional
- [ ] Gemini 3 Flash para PRs solo-docs como check más barato
- [ ] Pasar a público cuando tengamos métricas de tasa de fallos de CI en 5+ repos
