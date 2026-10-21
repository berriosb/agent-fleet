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
| `skills/fleet-conventions/CHAIN.md` | El orden canónico de las skills, por fases. Fuente de verdad del encadenado. |
| `skills/pre-push-qa/` | Compuerta de calidad antes del push. Detecta el stack y corre lint + tests. |
| `skills/fleet-interview/` | Interroga el árbol de decisiones antes de implementar. |
| `skills/work-unit-commits/` | Un commit = un comportamiento entregable. Tests y docs con su código. |
| `skills/systematic-debugging/` | Causa raíz antes de parchar. Reproducción Red-Green ante cualquier bug o fallo de tests. |
| `skills/verification-before-completion/` | Evidencia antes de afirmaciones. |
| `skills/session-handoff/` | Cierre estructurado y traspaso de contexto en disco antes de compactar o rotar agentes. |
| `skills/domain-modeling/` | Glosario y ADRs: el vocabulario compartido del proyecto. |
| `skills/cognitive-doc-design/` | Docs que un revisor puede verificar sin reconstruir la historia. |
| `scripts/sync-conventions.py` | Proyecta `conventions.md` del vault a `references/`. Render determinista: sin fecha ni rutas locales. |
| `scripts/check-skills.py` | Frontmatter, glifos CJK, fences de código, flags replicados y consistencia de la cadena. Solo stdlib. |
| `scripts/check-install.py` | Estado de **tu máquina**: skills sin enlazar y copias divergentes en los perfiles de Hermes. |
| `scripts/verify-hook.sh` | Round-trip del gate: el hook acepta, consume y bloquea como debe. |
| `scripts/verify.sh` | Verificación del repo. Hermética: es lo que corre la CI. `--install` suma el estado de tu máquina. |
| `scripts/release.sh` | Mueve el tag `v1` (que es la release) al HEAD. Con `--push` lo publica. |
| `upstream/ATTRIBUTION.md` | De dónde viene cada skill y bajo qué licencia. |

## El flujo que encadenan

El orden canónico está en
[`skills/fleet-conventions/CHAIN.md`](skills/fleet-conventions/CHAIN.md). No es una lista
lineal: hay fases transversales, condicionales y repetibles.

```
Fase 0  fleet-conventions            ← reglas universales, se cargan una vez y rigen todo
          ↓
Fase 1  fleet-interview              ← ¿qué quieres realmente? decisiones resueltas antes de código
        domain-modeling              ← el vocabulario que cristalizó, por escrito
        work-unit-commits             ← el trabajo partido en commits antes de implementar
          ↓
Fase 2  systematic-debugging         ← bug o comportamiento inesperado, cuando aparece
        cognitive-doc-design         ← docs, READMEs, notas de arquitectura
          ↓
Fase 3  verification-before-completion ← ¿terminó? evidencia fresca, no afirmaciones
        pre-push-qa (chequeos)       ← ¿está sano? lint + types + tests, local, sin secrets
          ↓
Fase 4  work-unit-commits            ← ¿qué va en este commit? un comportamiento por commit
          ↓  git commit
Fase 5  pre-push-qa (marcador)       ← el marcador se genera DESPUÉS del commit
        cognitive-doc-design         ← el cuerpo del PR
          ↓  git push
Fase 6  session-handoff              ← ¿cierras sesión o traspasas? estado persistido en disco
```

Tres reglas que el diagrama no puede mostrar:

- **`verification-before-completion` es una puerta, no un paso.** Se dispara en cada
  afirmación de éxito: antes de commitear, antes de cambiar de tarea, antes de delegar.
- **`pre-push-qa` tiene dos momentos.** Los chequeos están en la fase 3; el **marcador**
  está en la fase 5 y se genera **después** del commit, porque el hook compara el hash del
  marcador contra el HEAD que se está pusheando. Si el QA corre antes del commit, el push
  se bloquea con `STALE MARKER ERROR`.
- **`systematic-debugging` no espera al push.** El gate solo ve lint, tipos y tests: un bug
  de lógica nunca llega ahí.

Cada skill declara su fase en su propia sección "En la cadena", y
`scripts/check-skills.py` verifica que CHAIN.md y los `SKILL.md` no se contradigan. El
orden no vive solo en este README.

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

Orden completo en `skills/fleet-conventions/CHAIN.md`.

1. `fleet-conventions` — reglas universales. Leer antes de empezar. (fase 0)
2. Antes de implementar algo no trivial: `fleet-interview`. (fase 1)
3. Al cambiar el vocabulario o escribir un ADR: `domain-modeling`. (fase 1)
4. Ante cualquier bug o fallo de tests: `systematic-debugging`. (fase 2)
5. Al escribir docs o el cuerpo de un PR: `cognitive-doc-design`. (fase 2)
6. Antes de declarar algo terminado o de commitear: `verification-before-completion`. (fase 3)
7. Antes de cada commit: `work-unit-commits`. (fase 4)
8. Antes de cada push: `pre-push-qa`. (fase 5)
9. Al cerrar sesión o compactar contexto: `session-handoff`. (fase 6)
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

El render es determinista: no lleva fecha ni rutas locales, así que el `--check` da el
mismo resultado hoy y dentro de un mes. La única fuente del `name` y la `description` del
archivo generado es el `SKILL.md` curado, así que no pueden divergir.

Para cambiar una regla: **edita el vault**, corré el sync, commiteá. Editar el `SKILL.md`
a mano es correcto para lo que el vault no cubre todavía, pero ese texto no se regenera
nunca.

## Verificación del repo

```bash
./scripts/verify.sh              # el repo: hermético, es lo que corre la CI
./scripts/verify.sh --install    # el repo + el estado de tu máquina
```

| Paso | Qué comprueba |
|---|---|
| `sync-conventions.py --check` | La referencia proyectada del vault está al día. |
| `check-skills.py` | Frontmatter, glifos CJK, fences, flags de CLI replicados y que CHAIN.md y los SKILL.md no se contradigan. |
| `verify-hook.sh` | El hook de push acepta un marcador válido, lo consume, y bloquea un marcador obsoleto o ausente. |
| `run.sh` | El gate pasa sobre el propio repo. |

La verificación del repo es **hermética**: da el mismo resultado en un clone limpio y en
tu máquina, y por eso es la que corre la CI. El estado de tu instalación (las skills
enlazadas en `~/.agents`, `~/.claude`, `~/.codex`, `~/.gemini`) es otra cosa: se
comprueba aparte con `python3 scripts/check-install.py`.

## Publicar una versión

Los repos consumidores invocan este repo con
`uses: berriosb/agent-fleet/.github/workflows/qa.yml@v1`, y ese workflow hace checkout del runner
en `ref: v1`. El tag `v1` **es** la release: si no se mueve junto con el runner, los arreglos al
gate no llegan a los consumidores y el fallo aparece en el repo de otro.

```bash
./scripts/release.sh          # deja el tag v1 en HEAD, local
./scripts/release.sh --push   # lo publica en el remoto
```

El script verifica que el working tree esté limpio y que el repo pase su verificación antes de
mover nada. La CI lo vigila: el job `tag-drift` falla si `v1` no contiene el runner actual, y
solo corre en push a `main` (en un PR el tag todavía no puede incluir el cambio).

## Qué NO hace este repo

- **El camino local no pide API keys ni secrets remotos.** Todo es local y gratis. El
  workflow reusabe de CI (`qa.yml`) sí puede usar un LLM para el review y el auto-fix:
  es opt-in y se activa con un secret del repo.
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