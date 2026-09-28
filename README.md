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
| `scripts/run.sh` | Runner local en bash que detecta el stack, corre linter/tests y genera el marcador `.git/pre-push-qa-ok`. |
| `examples/pre-push.sh` | Hook git `pre-push` **opcional** para quien quiera enforcement duro en la terminal. Apagado por defecto. |
| `prompts/review.md` | System prompt para review de código local por el propio agente (opcional, agnóstico al LLM). |
| `prompts/auto-fix.md` | Prompt de auto-fix mecánico para el agente bajo supervisión humana (HITL). |

## Instalación

### Método 1: Vía `skills.sh` (Recomendado — 1 comando para todos tus agentes)

Compatible nativamente con el ecosistema de [skills.sh](https://skills.sh). Instala la skill automáticamente para todos los agentes detectados en tu máquina (**Claude Code, Antigravity `agy`, Cursor, Codex, Gemini CLI, OpenCode, GitHub Copilot, Cline, Zed, Warp**, etc.):

```bash
# Instalación global (recomendada para todos tus proyectos y agentes):
npx skills add berriosb/pre-push-qa -g

# O para un único proyecto local:
npx skills add berriosb/pre-push-qa
```

---

### Método 2: Instalación manual (Vía Git Clone / Symlinks)

Si prefieres clonar el repositorio y gestionar los enlaces simbólicos manualmente:

```bash
git clone https://github.com/berriosb/pre-push-qa.git ~/Proyectos/pre-push-qa
SRC="$HOME/Proyectos/pre-push-qa/skills/pre-push-qa"

for dest in \
  "$HOME/.claude/skills/pre-push-qa" \
  "$HOME/.config/opencode/skills/pre-push-qa" \
  "$HOME/.codex/skills/pre-push-qa" \
  "$HOME/.gemini/skills/pre-push-qa" \
  "$HOME/.agents/skills/pre-push-qa"; do
    mkdir -p "$dest"
    ln -sf "$SRC/SKILL.md" "$dest/SKILL.md"
done

# Opcional: Ejecución global en terminal vía ~/.local/bin
mkdir -p "$HOME/.local/bin"
ln -sf "$HOME/Proyectos/pre-push-qa/scripts/run.sh" "$HOME/.local/bin/pre-push-qa"
```

Verificar:
```bash
npx skills list -g
# O inspeccionar directamente:
ls -la ~/.claude/skills/pre-push-qa/SKILL.md
ls -la ~/.agents/skills/pre-push-qa/SKILL.md
agy -p "list the available skills" 2>&1 | head -10
```

> **Nota para Antigravity CLI (`agy`):** Para que `agy` cargue globalmente las skills ubicadas en `~/.agents/skills/`, asegúrate de registrar la ruta en `~/.gemini/config/skills.json`:
> ```json
> {
>   "entries": [
>     { "path": "~/.agents/skills" }
>   ]
> }
> ```

## Cómo funciona el gate local

Cuando le dices a tu agente "hacé push", "subí los cambios" o "revisá antes de pushear", la skill:

1. **Auto-detecta el stack del repositorio (orden de precedencia, primero detectado gana):**
   - **pnpm** (`pnpm-lock.yaml`): corre `pnpm install --frozen-lockfile`, `pnpm run lint`, `tsc --noEmit`, `pnpm test`.
   - **yarn** (`yarn.lock`): corre `yarn install --frozen-lockfile`, `yarn run lint`, `tsc --noEmit`, `yarn test`.
   - **bun** (`bun.lockb` o `bun.lock`): corre `bun install --frozen-lockfile`, `bun run lint`, `tsc --noEmit`, `bun test`.
   - **npm** (`package-lock.json` o fallback `package.json`): corre `npm ci`, `npm run lint`, `tsc --noEmit`, `npm test`.
   - **Python (uv)** (`uv.lock` o `pyproject.toml`): corre `uv sync`, `ruff check`, `mypy`, `pytest` (con fallback a ruff/mypy/pytest locales si uv no está presente). Si además hay `Dockerfile`, agrega `hadolint`.
   - **Python (pip)** (`requirements.txt` sin manifests uv): corre `pip install -r requirements.txt`, `ruff check`. Auto-detecta `pytest` o `unittest` si existen `tests/` o `test/`. Si hay `Dockerfile`, agrega `hadolint`.
   - **Docker** (`Dockerfile` o `docker-compose.{yml,yaml}`): corre `hadolint Dockerfile`.
   - **Terraform** (`*.tf` en raíz o subdir hasta 4 niveles): corre `terraform fmt -check -recursive`.
   - **Docs** (`*.md` solamente): se salta lint/tests de código para no gastar tiempo.
   - **Mixed** (ninguno detectado): corre `pnpm` + `python` en paralelo como fallback.

2. **Ejecuta static + tests:** Si algo falla, **detiene el push** y pide corregir antes de continuar.
3. **Push-guard:** Valida que el árbol de trabajo esté limpio y que todas las comprobaciones hayan salido con código `0`.

También puedes ejecutar este chequeo directamente desde tu terminal en cualquier proyecto con:
```bash
pre-push-qa   # Si creaste el symlink en ~/.local/bin/pre-push-qa
# o directamente desde la raíz del repo:
./scripts/run.sh
```
Si pasa, crea el marcador de verificación en `.git/pre-push-qa-ok` con el hash del commit actual.

## Hook de git opcional (Enforcement duro)

Si quieres que `git push` siempre exija haber pasado el QA antes de permitir el envío:

```bash
mkdir -p ~/.githooks
cp examples/pre-push.sh ~/.githooks/pre-push
chmod +x ~/.githooks/pre-push
git config --global core.hooksPath ~/.githooks
```

El hook bloqueará cualquier push en la terminal a menos que:
1. Exista el marcador válido en `.git/pre-push-qa-ok` correspondiente al commit HEAD actual (creado por la skill o `run.sh`), el cual es consumido al hacer push para evitar reusar aprobaciones viejas, o
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
