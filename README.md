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

**Las tres skills de Hermes no van en el paquete público.** Llevan
`metadata.internal: true`, que es lo que el CLI respeta: no aparecen en el
descubrimiento y no se instalan. Son para la flota del autor, no para el mundo.
Si las quieres:

```bash
npx skills add berriosb/agent-fleet -g --skill hermes-agent    # una puntual
INSTALL_INTERNAL_SKILLS=1 npx skills add berriosb/agent-fleet -g  # todas
```

En la máquina del autor, `scripts/install.sh` las enlaza igual: la distinción es
entre el paquete público y la instalación local.

## Qué hay acá

| Ruta | Qué es |
|---|---|
| `skills/fleet-conventions/` | Las reglas que aplican a todo agente: verificación, idioma, datos, borrado, entregables. |
| `skills/hermes-agent/` | Guía de operación de Hermes: configurar, extender, depurar y auditar un perfil del fleet.  (interna)|
| `skills/hermes-fleet-audit/` | Auditoría del fleet: inventario de skills por perfil, drift, uso real, memoria y plugins.  (interna)|
| `skills/fleet-conventions/CHAIN.md` | El orden canónico de las skills, por fases. Fuente de verdad del encadenado. |
| `skills/pre-push-qa/` | Compuerta de calidad antes del push. Detecta el stack y corre lint + tests. |
| `skills/fleet-interview/` | Interroga el árbol de decisiones antes de implementar. |
| `skills/fleet-backlog/` | Parte una idea en historias de usuario verticales, de una línea cada una. |
| `skills/fleet-story/` | Refina UNA historia: criterios de aceptación, out of scope y plan mínimo. |
| `skills/fleet-pair/` | Escribe el código en pasos testeados: un test, código mínimo, verde. |
| `skills/work-unit-commits/` | Un commit = un comportamiento entregable. Tests y docs con su código. |
| `skills/systematic-debugging/` | Causa raíz antes de parchar. Reproducción Red-Green ante cualquier bug o fallo de tests. |
| `skills/hermes-profile-audit/` | Auditoría de un perfil de Hermes: config declarado contra realidad, plugins, memoria y logs.  (interna)|
| `skills/verification-before-completion/` | Evidencia antes de afirmaciones. |
| `skills/session-handoff/` | Cierre estructurado y traspaso de contexto en disco antes de compactar o rotar agentes. |
| `skills/domain-modeling/` | Glosario y ADRs: el vocabulario compartido del proyecto. |
| `skills/cognitive-doc-design/` | Docs que un revisor puede verificar sin reconstruir la historia. |
| `scripts/sync-conventions.py` | Proyecta `conventions.md` del vault a `references/`. Render determinista: sin fecha ni rutas locales. |
| `scripts/check-skills.py` | Frontmatter, glifos CJK, fences de código, flags replicados y consistencia de la cadena. Solo stdlib. |
| `scripts/check-install.py` | Estado de **tu máquina**: skills sin enlazar y copias divergentes en los perfiles de Hermes. |
| `scripts/verify-hook.sh` | Round-trip del gate: el hook acepta, consume y bloquea como debe. |
| `scripts/verify-runner.sh` | Round-trip del runner: omite lo que no tiene, bloquea lo que falla, reparte por scope. |
| `scripts/verify.sh` | Verificación del repo. Hermética: es lo que corre la CI. `--install` suma el estado de tu máquina. |
| `scripts/install.sh` | Instala las skills en los cuatro roots donde los agentes las buscan, y deja la máquina en el estado que `check-install.py` exige. |
| `scripts/install-dev-tools.sh` | Instala `ruff`, `mypy` y `pytest` desde `requirements-dev.txt`. La CI lee el mismo archivo. |
| `scripts/release.sh` | Mueve el tag `v1` (que es la release) al HEAD. Con `--push` lo publica. |
| `requirements-dev.txt` | Las herramientas de QA del repo. Es la única declaración: la leen la CI y el local. |
| `upstream/ATTRIBUTION.md` | De dónde viene cada skill y bajo qué licencia. |
| `CHANGELOG.md` | Los cambios del repo, por tema. El tag `v1` se mueve en cada push, así que no hay versiones que numerar. |

## El flujo que encadenan

El orden canónico está en
[`skills/fleet-conventions/CHAIN.md`](skills/fleet-conventions/CHAIN.md). No es una lista
lineal: hay fases transversales, condicionales y repetibles.

```
Fase 0  fleet-conventions            ← reglas universales, se cargan una vez y rigen todo
        hermes-agent                 ← configurar, extender o depurar Hermes mismo
          ↓
Fase 1  fleet-interview              ← ¿qué quieres realmente? decisiones resueltas antes de código
        fleet-backlog                ← la idea partida en historias verticales (explícita)
        fleet-story                  ← UNA historia refinada: criterios + out of scope (explícita)
        domain-modeling              ← el vocabulario que cristalizó, por escrito
        work-unit-commits             ← el trabajo partido en commits antes de implementar
          ↓
Fase 2  fleet-pair                   ← la historia implementada en pasos testeados (explícita)
        systematic-debugging         ← bug o comportamiento inesperado, cuando aparece
        cognitive-doc-design         ← docs, READMEs, notas de arquitectura
          ↓
Fase 3  verification-before-completion ← ¿terminó? evidencia fresca, no afirmaciones
        pre-push-qa (chequeos)       ← ¿está sano? lint + types + tests, local, sin secrets
        systematic-debugging         ← cuando lo que falla es el gate
          ↓
Fase 4  hermes-profile-audit         ← auditar UN perfil del fleet (track por evento)
        hermes-fleet-audit          ← auditar el fleet entero
          ↓
Fase 5  fleet-pair                   ← el gate ya pasó: ahora sí, el commit
        work-unit-commits            ← ¿qué va en este commit? un comportamiento por commit
          ↓  git commit
Fase 6  pre-push-qa (marcador)       ← el marcador se genera DESPUÉS del commit
        cognitive-doc-design         ← el cuerpo del PR
          ↓  git push
Fase 7  session-handoff              ← ¿cierras sesión o traspasas? estado persistido en disco
```

Las fases 2, 3 y 4 se repiten **por unidad de trabajo**: se escribe el código, el gate
corre antes del commit, y recién después se commitea. Ningún commit entra al historial
sin haber pasado el gate.

`fleet-backlog`, `fleet-story` y `fleet-pair` se invocan **por nombre**: arrancan un
flujo con checkpoints humanos, así que el agente no las dispara solo. El modelo que
conviene usar en cada fase está en la tabla de
[`CHAIN.md`](skills/fleet-conventions/CHAIN.md).

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
git clone https://github.com/berriosb/agent-fleet.git ~/Proyectos/agent-fleet
~/Proyectos/agent-fleet/scripts/install.sh
```

El script deja la máquina en el estado que el repo exige:

- Enlaza el **directorio completo** de cada skill (no solo `SKILL.md`: sin
  `scripts/` y `prompts/` el agente no puede correr el runner) en los cuatro
  roots donde los agentes las buscan: `~/.agents/skills`, `~/.claude/skills`,
  `~/.codex/skills` y `~/.gemini/skills`.
- Deja el runner en `~/.local/bin/pre-push-qa`.
- Resuelve las copias divergentes de estas skills en los perfiles de Hermes,
  reemplazándolas por enlaces al repo.
- Al final corre `check-install.py`, así que el resultado no es una promesa.

Lo que reemplaza va a la papelera (`gio trash`), no se borra. Con `--hook`
instala además el hook global de push (enforcement duro).

### Con el CLI de skills

```bash
npx skills add berriosb/agent-fleet -g
```

Deja las skills en `~/.agents/skills/`, de donde leen OpenCode, Amp, Antigravity,
Cline y unos veinte más. **No** las deja en `~/.claude/skills`, `~/.codex/skills`
ni `~/.gemini/skills`: Claude Code, Codex y Gemini leen roots propios. Para
cubrir esos tres, corre `scripts/install.sh` después.

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

Para un repo donde quieras que las reglas viajen con el código.

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

`fleet-backlog`, `fleet-story` y `fleet-pair` **no van en la lista**: se invocan por
nombre (`/fleet-backlog`, `/fleet-story`, `/fleet-pair`) porque arrancan un flujo con
checkpoints humanos.

Una salvedad que importa: el `disable-model-invocation: true` del frontmatter es una
extensión de **Claude Code**, no del
[estándar Agent Skills](https://agentskills.io/specification). En OpenCode, Codex y
Gemini el campo se ignora y la skill se carga cuando su `description` matchea, como
las demás. Por eso el texto `Trigger: ...` de las tres descripciones no es decorativo:
es lo que las mantiene apagadas fuera de Claude Code.

## Cómo funciona el gate de `pre-push-qa`

Detecta el stack del repo (primero detectado gana) y corre las herramientas nativas del
proyecto, sin secrets ni configuración externa:

| Stack | Qué corre |
|---|---|
| **pnpm** / **yarn** / **bun** / **npm** | install con lockfile, lint, `tsc --noEmit`, tests, build |
| **Python (uv)** | `uv sync`, `ruff`, `mypy`, `pytest`, `hadolint` si hay Dockerfile |
| **Python (pip)** | `pip install -r requirements.txt`, `ruff`, autodetección de `pytest`/`unittest` |
| **Go** | `go vet ./...`, `go test ./...` |
| **Rust** | `cargo check --all-targets`, `cargo test` |
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

### Fallos que ya existían (baseline)

Un repo puede tener tests que ya fallaban antes de que nadie tocara nada. Bloquear el push
por eso deja al repo sin poder pushear nunca. El **baseline** es un archivo en la raíz del
repo (`pre-push-qa-baseline.txt`) con los tests que ya se sabe que fallan: solo los fallos
*fuera* de esa lista bloquean.

```bash
# Genera el baseline con los tests que fallan ahora mismo
pre-push-qa --update-baseline      # o: bash skills/pre-push-qa/scripts/run.sh --update-baseline

git add pre-push-qa-baseline.txt && git commit -m "chore(qa): baseline de fallos conocidos"
```

El archivo va commiteado a propósito: es la lista de fallos que el proyecto decide tolerar, y
tiene que ser visible en el PR que la agrega. Cuando la suite falla, el gate reporta
`baseline-failures exist; new failures: <lista>`.

Si el runner no logra identificar qué tests fallaron, **bloquea**: el gate nunca se debilita
porque no entendió la salida de un runner.

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

Para cambiar una regla: **edita el vault**, corre el sync, commitea. Editar el `SKILL.md`
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
| `check-skills.py` | Frontmatter, glifos CJK, fences, flags de CLI replicados, que CHAIN.md y los SKILL.md no se contradigan, que la CI **ejecute** el gate y no solo lo mencione, que cada skill esté **enlazada** en `.agents/skills/`, y que el diagrama de este README coincida con `CHAIN.md`. |
| `verify-hook.sh` | El hook de push acepta un marcador válido, lo consume, y bloquea un marcador obsoleto o ausente. |
| `verify-runner.sh` | El runner omite las herramientas que el proyecto no tiene, bloquea las que fallan, y respeta `--scope`. |
| `run.sh` | El gate pasa sobre el propio repo. |

El primer paso necesita el vault: en local, en disco; en CI, el secret `VAULT_TOKEN`
del repo. Si el vault no está accesible, el paso **no puede comparar** — y en CI eso
es un fallo explícito (`--require-vault`), no un verde vacío.

La verificación del repo es **hermética**: da el mismo resultado en un clone limpio y en
tu máquina, y por eso es la que corre la CI. El estado de tu instalación (las skills
enlazadas en `~/.agents`, `~/.claude`, `~/.codex`, `~/.gemini`) es otra cosa: se
comprueba aparte con `python3 scripts/check-install.py`.

El typecheck local (`mypy`) solo corre si está instalado. Para que local y CI
apliquen los mismos criterios:

```bash
./scripts/install-dev-tools.sh    # ruff, mypy y pytest, desde requirements-dev.txt
```

## Qué cambia para los repos que usan el workflow

El workflow reusable dejó de ser decorativo. Antes los jobs de `lint` y de `tests`
terminaban en `|| true` y los tests iban por un pipe que devolvía el código de
`tail`: **un PR con lint roto y una suite en rojo pasaban los dos**. Ahora los dos
jobs ejecutan el runner y fallan de verdad.

Consecuencias al actualizar a `v1`:

| Cambio | Qué se ve |
|---|---|
| El job de lint y tipos falla si hay lint o errores de tipo | PRs que antes pasaban en verde ahora se ponen rojos |
| El job de tests falla si la suite falla | Ídem |
| `auto-fix` dispara de verdad | Se abre una rama `auto/fix-<run>` en vez de no hacer nada |
| El shellcheck del stack `mixed` ahora corre | Un script con problemas de shell bloquea el push |
| Los repos Python sin manifiesto ahora se lintean | Antes pasaban sin que se mirara nada |

Y lo que **no** cambia: una herramienta que el proyecto no tiene no es un fallo.
Si `mypy` no está en el entorno del proyecto ni en el PATH, el typecheck se
reporta como omitido. El gate bloquea por los problemas que encuentra, nunca por
las herramientas que no pidió.

Si no quieres que el gate bloquee, no uses el workflow reusable en ese repo: es
opt-in por repo, y el camino local (`pre-push-qa`) se puede dejar como aviso.

## Publicar una versión

Los repos consumidores invocan este repo con
`uses: berriosb/agent-fleet/.github/workflows/qa.yml@v1`, y ese workflow hace checkout del runner
en `ref: v1`. El tag `v1` **es** la release: si no se mueve junto con el runner, los arreglos al
gate no llegan a los consumidores y el fallo aparece en el repo de otro.

**El tag se mueve solo.** Cada push a `main` dispara el workflow `release`, que lo mueve al commit
publicado. No hay paso manual que se pueda olvidar: el tag estuvo 13 commits atrasado sin que nada
lo dijera, y ahora lo dice la CI.

Para hacerlo a mano (por ejemplo, si la CI no está disponible):

```bash
./scripts/release.sh          # deja el tag v1 en HEAD, local
./scripts/release.sh --push   # lo publica en el remoto
```

El script verifica que el working tree esté limpio y que el repo pase su verificación antes de
mover nada. El tag **solo avanza**: con dos pushes seguidos a `main`, el run que tarda más no
puede dejarlo atrasado. Con `--force` se puede mover a propósito hacia atrás.

La CI lo vigila: el job `tag-drift` de `validate.yml` espera a que el tag alcance el runner actual
y falla si no llega. Espera, y no falla al primer intento, porque el workflow `release` corre en
paralelo: si el release falla, el tag no llega y el job falla al expirar la espera.

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

- [x] Tests baseline-aware (no romper si el test ya fallaba antes del diff)
- [x] Detección ampliada de stacks (Go `go test ./...`, Rust `cargo check && cargo test`)
- [ ] `to-spec` / `to-tickets` / `code-review` cuando haya issue tracker configurado

## Licencia

MIT para lo propio. Las skills adaptadas conservan su licencia original: MIT
(`verification-before-completion`, `domain-modeling`, `fleet-interview`) y Apache-2.0
(`work-unit-commits`, `cognitive-doc-design`, `pre-push-qa`). Ver
[`upstream/ATTRIBUTION.md`](upstream/ATTRIBUTION.md) para el detalle y los avisos exigidos
por Apache-2.0.