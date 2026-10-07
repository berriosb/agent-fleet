# agent-fleet

Contrato de trabajo para todos los agentes de Bastián. Una skill de QA antes del push ya
existe y ahora vive acá; este repo la agrupa con el resto de la estructura: cómo alinearse
antes de escribir, cómo partir el trabajo, cómo verificar, y las reglas que ningún agente
debe saltarse.

**Un comando, todos los agentes:**

```bash
npx skills add berriosb/agent-fleet -g
```

Funciona con Claude Code, Codex, OpenCode, agy, Gemini CLI, Copilot CLI, Cursor, pi,
mcode, y cualquier otro cliente del [estándar Agent Skills](https://agentskills.io).

## Qué hay acá

| Ruta | Qué es |
|---|---|
| `skills/fleet-conventions/` | Las reglas que aplican a todo agente: verificación, idioma, datos, borrado, entregables. |
| `skills/pre-push-qa/` | Compuerta de calidad antes del push. Detecta el stack y corre lint + tests. |
| `skills/fleet-interview/` | Interroga el árbol de decisiones antes de implementar. |
| `skills/work-unit-commits/` | Un commit = un comportamiento entregable. Tests y docs con su código. |
| `skills/verification-before-completion/` | Evidencia antes de afirmaciones. |
| `skills/domain-modeling/` | Glosario y ADRs: el vocabulario compartido del proyecto. |
| `skills/cognitive-doc-design/` | Docs que un revisor puede verificar sin reconstruir la historia. |
| `scripts/sync-conventions.py` | Proyecta `conventions.md` del vault a `references/`. |
| `upstream/ATTRIBUTION.md` | De dónde viene cada skill y bajo qué licencia. |

## El flujo que encadenan

```
fleet-interview   ← ¿qué querés realmente? decisiones resueltas antes de código
      ↓
work-unit-commits ← ¿qué va en cada commit? un comportamiento por commit
      ↓
pre-push-qa       ← ¿está sano? lint + types + tests, local, sin secrets
      ↓
verification-before-completion  ← ¿terminó? evidencia fresca, no afirmaciones
      ↓
cognitive-doc-design           ← ¿se entiende? docs que un revisor puede chequear
```

Ninguna es obligatoria por sí sola. La cadena es el valor: juntas cambian *cuándo* se
detecta un error, no solo si se detecta.

## Instalación

### Global (recomendado)

```bash
npx skills add berriosb/agent-fleet -g
```

Instala en todos los agentes detectados en la máquina.

### Manual (symlinks)

```bash
git clone https://github.com/berriosb/agent-fleet.git ~/Proyectos/agent-fleet
SRC="$HOME/Proyectos/agent-fleet/skills"

# Enlaza el DIRECTORIO, no solo SKILL.md — sin scripts/ y examples/ el agente
# no puede correr el runner ni el hook que documenta pre-push-qa.
for dest in \
  "$HOME/.agents/skills" \
  "$HOME/.claude/skills" \
  "$HOME/.codex/skills" \
  "$HOME/.gemini/skills"; do
  for skill in "$SRC"/*/; do
    name=$(basename "$skill")
    mkdir -p "$dest"
    ln -sfn "$skill" "$dest/$name"
  done
done

# Ejecución global en terminal
mkdir -p "$HOME/.local/bin"
ln -sf "$SRC/pre-push-qa/scripts/run.sh" "$HOME/.local/bin/pre-push-qa"

# Hook global (todos los repos lo heredan vía core.hooksPath)
mkdir -p "$HOME/.githooks"
cp "$SRC/pre-push-qa/examples/pre-push.sh" "$HOME/.githooks/pre-push"
chmod +x "$HOME/.githooks/pre-push"
git config --global core.hooksPath "$HOME/.githooks"
```

Verificar:

```bash
npx skills list -g
ls ~/.agents/skills/fleet-conventions/SKILL.md
pre-push-qa        # desde cualquier repo
```

> **Antigravity CLI (`agy`)**: para que cargue globalmente las skills de `~/.agents/skills/`,
> registralo en `~/.gemini/config/skills.json`:
> ```json
> { "entries": [ { "path": "~/.agents/skills" } ] }
> ```

### Por proyecto

```bash
npx skills add berriosb/agent-fleet          # ./<agent>/skills/, commiteado
```

Para un repo donde querés que las reglas viajen con el código.

## Bootstrap: las skills no son obligatorias por sí solas

Una skill se carga **si su description matchea**. Para que se carguen siempre, declaralas
en el archivo de instrucciones del agente. Sin esto, la cadena es opcional.

| Agente | Archivo a editar |
|---|---|
| Claude Code | `~/.claude/CLAUDE.md` |
| Codex | `~/.codex/AGENTS.md` |
| OpenCode | `~/.config/opencode/AGENTS.md` (`instructions` en `opencode.json`) |
| agy / Gemini CLI | `~/.gemini/GEMINI.md` |
| Hermes | `~/.hermes/profiles/<perfil>/AGENTS.md` |
| Cualquier otro que soporte AGENTS.md | `AGENTS.md` en la raíz del proyecto |

Contenido mínimo:

```markdown
## agent-fleet (aplica a TODO trabajo)

1. `fleet-conventions` — reglas universales. Leer antes de empezar.
2. Antes de implementar algo no trivial: `fleet-interview`.
3. Antes de cada commit: `work-unit-commits`.
4. Antes de cada push: `pre-push-qa`.
5. Antes de declarar algo terminado: `verification-before-completion`.
```

## Cómo funciona el gate de `pre-push-qa`

Detecta el stack del repo (primero detectado gana) y corre las herramientas nativas del
proyecto, sin secrets ni configuración externa:

| Stack | Qué corre |
|---|---|
| **pnpm** / **yarn** / **bun** / **npm** | install con lockfile, lint, `tsc --noEmit`, tests, build |
| **Python (uv)** | `uv sync`, `ruff`, `mypy`, `pytest`, `hadolint` si hay Dockerfile |
| **Python (pip)** | `pip install -r requirements.txt`, `ruff`, autodetección de `pytest`/`unittest` |
| **Docker** | `hadolint` |
| **Terraform** | `terraform fmt -check -recursive` |
| **Docs** | se salta lint/tests de código |

Si algo falla, **detiene el push**. Si todo pasa, crea el marcador `.git/pre-push-qa-ok`
con el hash del commit actual.

### Hook de git opcional (enforcement duro)

```bash
cp skills/pre-push-qa/examples/pre-push.sh ~/.githooks/pre-push
chmod +x ~/.githooks/pre-push
git config --global core.hooksPath ~/.githooks
```

El hook bloquea cualquier push en la terminal a menos que exista un marcador válido para
el HEAD actual, o uses `git push --no-verify` de forma consciente. El marcador se consume
al pushear, así no se reusan aprobaciones viejas.

## Cómo se mantiene `fleet-conventions`

La fuente de verdad es `Agent-Shared/conventions.md` en el vault Obsidian, no este repo.
`skills/fleet-conventions/SKILL.md` es una curación legible por agentes que no abren el
vault; `references/vault-conventions.md` es la proyección literal, regenerable:

```bash
python3 scripts/sync-conventions.py            # actualizar
python3 scripts/sync-conventions.py --check    # solo comparar (exit 1 si difiere)
```

Para cambiar una regla: **editá el vault**, corré el sync, commiteá. Editar el `SKILL.md`
a mano es correcto para lo que el vault no cubre todavía, pero ese texto no se regenera
nunca.

## Qué NO hace este repo

- **No pide API keys ni secrets remotos.** Todo es local y gratis.
- **No toca la CI de tus repos.** Cada repo mantiene sus propios workflows.
- **No enforce `--force` ni `--no-verify`.** El hook es opcional y desactivable a propósito.
- **No hace secret scanning.** Complemento recomendado: `push-gate` (Gitleaks).
- **No es el lugar de las skills de dominio.** Las de datos viven en
  [`berriosb/data-analytics-agents`](https://github.com/berriosb/data-analytics-agents).
- **No reemplaza tu criterio.** El gate detiene pushes rotos; no decide si el cambio vale
  la pena.

## Roadmap

- [ ] Tests baseline-aware (no romper si el test ya fallaba antes del diff)
- [ ] Detección ampliada de stacks (Go `go test ./...`, Rust `cargo check && cargo test`)
- [ ] `to-spec` / `to-tickets` / `code-review` cuando haya issue tracker configurado

## Licencia

MIT para lo propio. Las skills adaptadas conservan su licencia original: MIT
(`verification-before-completion`, `domain-modeling`, `fleet-interview`) y Apache-2.0
(`work-unit-commits`, `cognitive-doc-design`, `pre-push-qa`). Ver
[`upstream/ATTRIBUTION.md`](upstream/ATTRIBUTION.md) para el detalle y los avisos exigidos
por Apache-2.0.