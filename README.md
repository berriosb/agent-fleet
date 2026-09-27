# pre-push-qa

Compuerta de calidad pre-push agnóstica al agente. Corre lint, tests y un push-guard en
cualquiera de tus agentes (Codex, OpenCode, Antigravity `agy`, Gemini CLI, Claude Code
o terminal) antes de un `git push`.

**Objetivo:** Evitar que commits rotos lleguen a GitHub o rompan la integración continua.
Funciona 100% en local y sin fricción: los agentes ejecutan las validaciones directamente con
las herramientas nativas de tu proyecto (`uv`, `ruff`, `pytest`, `pnpm`, `npm`, `tsc`, `terraform`),
sin necesidad de configurar secrets, llaves externas ni workflows invasivos en tus repositorios.

## Qué hay en este repo

| Ruta | Qué es |
|---|---|
| `skills/pre-push-qa/SKILL.md` | La skill del agente. Symlink en el path de skills de cada agente. |
| `scripts/run.sh` | Runner local en bash que detecta el stack, corre linter/tests y genera el marcador `.pre-push-qa-ok`. |
| `examples/pre-push.sh` | Hook git `pre-push` **opcional** para quien quiera enforcement duro en la terminal. Apagado por defecto. |
| `prompts/review.md` | System prompt para review de código local por el propio agente (opcional, agnóstico al LLM). |
| `prompts/auto-fix.md` | Prompt de auto-fix mecánico para el agente bajo supervisión humana (HITL). |

## Instalar la skill en cada agente (5 symlinks, 30 segundos)

```bash
# Path a este repo clonado
SRC="$HOME/Proyectos/pre-push-qa/skills/pre-push-qa"
# O si usas perfil Hermes:
# SRC="$HOME/.hermes/profiles/codehak/skills/software-development/pre-push-qa"

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

Verificar:
```bash
ls -la ~/.claude/skills/pre-push-qa/SKILL.md
ls -la ~/.agents/skills/pre-push-qa/SKILL.md
agy -p "list the available skills" 2>&1 | head -10
```

## Cómo funciona el gate local

Cuando le dices a tu agente "hacé push", "subí los cambios" o "revisá antes de pushear", la skill:

1. **Auto-detecta el stack del repositorio (orden de precedencia, primero detectado gana):**
   - **pnpm** (`pnpm-lock.yaml`): corre `pnpm install --frozen-lockfile`, `pnpm run lint`, `tsc --noEmit`.
   - **npm** (`package-lock.json`): corre `npm ci`, `npm run lint`, `tsc --noEmit`.
   - **Python (uv)** (`uv.lock` o `pyproject.toml`): corre `uv sync`, `ruff check`, `mypy`, `pytest`. Si además hay `Dockerfile`, agrega `hadolint`.
   - **Python (pip)** (`requirements.txt` sin manifests uv): corre `pip install -r requirements.txt`, `ruff check`. Auto-detecta `pytest` o `unittest` si existen `tests/` o `test/`. Si hay `Dockerfile`, agrega `hadolint`.
   - **Docker** (`Dockerfile` o `docker-compose.{yml,yaml}`): corre `hadolint Dockerfile`.
   - **Terraform** (`*.tf` en raíz o subdir hasta 4 niveles): corre `terraform fmt -check -recursive`.
   - **Docs** (`*.md` solamente): se salta lint/tests de código para no gastar tiempo.
   - **Mixed** (ninguno detectado): corre `pnpm` + `python` en paralelo como fallback.

2. **Ejecuta static + tests:** Si algo falla, **detiene el push** y pide corregir antes de continuar.
3. **Push-guard:** Valida que el árbol de trabajo esté limpio y que todas las comprobaciones hayan salido con código `0`.

También puedes ejecutar este chequeo directamente desde tu terminal con:
```bash
./scripts/run.sh
```
Si pasa, crea el marcador `.pre-push-qa-ok` en la raíz del repo.

## Hook de git opcional (Enforcement duro)

Si quieres que `git push` siempre exija haber pasado el QA antes de permitir el envío:

```bash
mkdir -p ~/.githooks
cp examples/pre-push.sh ~/.githooks/pre-push
chmod +x ~/.githooks/pre-push
git config --global core.hooksPath ~/.githooks
```

El hook bloqueará cualquier push en la terminal a menos que:
1. Exista el marcador `.pre-push-qa-ok` creado por la skill o `run.sh`, o
2. Se use `git push --no-verify` de manera consciente.

## Qué NO hace esta skill

- **No requiere API keys ni secrets remotos:** Los tests y linters son 100% locales y gratuitos.
- **No ensucia repositorios con bots ni PRs automáticos en CI:** Cada repositorio mantiene sus propios flujos de CI estándar.
- **No es git hook por defecto:** Es una skill que el agente ejecuta por iniciativa o solicitud. Si quieres enforcement duro a nivel de git, usa `examples/pre-push.sh`.
- **No enforce `git push --force` ni `--no-verify`.** Para eso, sumá el skill
  [`block-no-verify-hook`](https://www.skills.sh/wshobson/agents/block-no-verify-hook) como complemento.
- **No hace secret scanning:** Recomendado como complemento:
  [`push-gate`](https://www.skills.sh/0xdarkmatter/claude-mods/push-gate) que usa Gitleaks.

## Roadmap

- [ ] Manejo de tests baseline-aware (no romper si el test ya fallaba antes del diff en la rama base)
- [ ] Detección ampliada de stacks (Go `go test ./...`, Rust `cargo check && cargo test`)
- [ ] Plugins de reporting enriquecido en terminal para agentes interactivos
