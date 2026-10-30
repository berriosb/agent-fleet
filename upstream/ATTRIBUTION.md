# Attribution

Este repo mezcla material propio con skills adaptadas de terceros. Cada skill conserva la
licencia de su origen. Los avisos exigidos por Apache-2.0 están en `NOTICE`.

## Skills propias

| Skill | Autor | Licencia |
|---|---|---|
| `fleet-conventions` | Bastián Berrios | MIT |
| `session-handoff` | Bastián Berrios | MIT |
| `hermes-fleet-audit` | Bastián Berrios | MIT |
| `hermes-profile-audit` | Bastián Berrios | MIT |

## Skills adaptadas

| Skill | Origen | Licencia | Cambios |
|---|---|---|---|
| `pre-push-qa` | Propio (historial migrado desde `berriosb/pre-push-qa`) | MIT | developing. Ver "Auditoría 2026-10-20". |
| `hermes-agent` | [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent) `skills/autonomous-ai-agents/hermes-agent` | MIT | Copia exacta del upstream v3.2.0 (fork `berriosb/hermes-agent`), mas la seccion "En la cadena" con la fase. Frontmatter normalizado (`version`, `license`, `platforms`, `metadata.hermes`). Las referencias propias del fleet se movieron a la skill `hermes-fleet-audit` para que esta siga siguiendo al upstream. Description reescrita con ruteo explicito (ver "Ruteo por description"). Se agrega `references/vault-memory-stack.md` (stack de memoria de vault para Hermes) con su fila en la tabla de referencias. |
| `verification-before-completion` | [`obra/superpowers`](https://github.com/obra/superpowers) `skills/verification-before-completion` | MIT | Frontmatter normalizado (se agrega `license` y `version`). Se agrega la seccion "En la cadena" con la fase. Se agrega la seccion "No Skip". Description reescrita con ruteo explicito (ver "Ruteo por description"). El resto del cuerpo queda sin cambios. |
| `systematic-debugging` | [`obra/superpowers`](https://github.com/obra/superpowers) `skills/systematic-debugging` | MIT | Incluye guías de soporte (`root-cause-tracing.md`, `defense-in-depth.md`, `condition-based-waiting.md`). Adaptada para eliminar prefijos `superpowers:*`. Frontmatter normalizado (se agrega `version`). Se agrega la seccion "En la cadena" con la fase. Description reescrita con ruteo explicito (ver "Ruteo por description"). |
| `domain-modeling` | [`mattpocock/skills`](https://github.com/mattpocock/skills) `skills/engineering/domain-modeling` | MIT | Incluye plantillas `GLOSSARY-FORMAT.md` y `ADR-FORMAT.md`. Frontmatter normalizado (se agrega `license` y `version`). Se agrega la seccion "En la cadena" con la fase. Description reescrita con ruteo explicito (ver "Ruteo por description"). |
| `fleet-interview` | [`mattpocock/skills`](https://github.com/mattpocock/skills) `skills/productivity/grilling` | MIT | Renombrada de `grilling` (directorio y `name` en frontmatter) para no colisionar con el original upstream. Description reescrita para que el trigger coincida con `AGENTS.md`. Frontmatter normalizado (se agrega `license` y `version`). Se agrega la seccion "En la cadena" con la fase. Ver nota abajo. |
| `work-unit-commits` | [`Gentleman-Programming/gentle-ai`](https://github.com/Gentleman-Programming/gentle-ai) `skills/work-unit-commits` | Apache-2.0 | Sección "ODD Relationship" reemplazada por "Evidence and Thresholds": se elimina el vocabulario de un framework ajeno (ODD) y se conservan las reglas exigibles. Frontmatter normalizado (`version` pasa de `metadata` a campo de primer nivel). Se agrega la seccion "En la cadena" con las fases. Se agrega la regla "Test with the code" y la seccion "The test's diff comes first". Description reescrita con ruteo explicito (ver "Ruteo por description"). |
| `cognitive-doc-design` | [`Gentleman-Programming/gentle-ai`](https://github.com/Gentleman-Programming/gentle-ai) `skills/cognitive-doc-design` | Apache-2.0 | Frontmatter normalizado (`version` pasa de `metadata` a campo de primer nivel). Se agrega la seccion "En la cadena" con las fases. La seccion "PR and Review Docs" pasa a definir la forma canonica del cuerpo del PR, que `pre-push-qa` replica. Description reescrita con ruteo explicito (ver "Ruteo por description"). |
| `fleet-backlog` | [`nschurmann/hola-ai`](https://github.com/nschurmann/hola-ai) `skills/backlog` | MIT | Renombrada de `backlog` (directorio y `name`) para no colisionar con el original upstream. Se agrega la seccion "En la cadena" con la fase. `CLAUDE.md` pasa a ser `AGENTS.md`. El tracker puede ser un `backlog.md` en el repo. Se agrega la regla "una cosa por historia". |
| `fleet-story` | [`nschurmann/hola-ai`](https://github.com/nschurmann/hola-ai) `skills/story` | MIT | Renombrada de `story` (directorio y `name`). Se agrega la seccion "En la cadena" con la fase. Se agrega la regla "out of scope is not optional". |
| `fleet-pair` | [`nschurmann/hola-ai`](https://github.com/nschurmann/hola-ai) `skills/pair` | MIT | Renombrada de `pair` (directorio y `name`). Se agrega la seccion "En la cadena" con la fase. El commit pasa a ser del agente siguiendo `work-unit-commits` (el upstream prohibe commitear), y lo precede el gate de la fase 3. `/code-review` se reemplaza por `verification-before-completion`. Se agrega la regla "el test cambia en el mismo commit que la implementacion". Description reescrita con ruteo explicito (ver "Ruteo por description"). |

### Ruteo por description

Todas las `description` del repo se reescribieron para que cada una diga tres cosas:
qué hace, cuándo aplica, y **a qué skill cede el caso que no es suyo**. La razón es
técnica, no de estilo: `CHAIN.md` es la fuente de verdad del orden, pero **`CHAIN.md` no
se carga por `description`**. En runtime lo único que decide qué skill entra es el texto
de la description. Con las descriptions anteriores, "voy a implementar esta feature"
cargaba cinco skills a la vez y el agente no tenía con qué elegir.

El formato es: qué hace + `Trigger:` + una serie de `NOT <caso> (<skill>)`.

`scripts/check-skills.py` lo verifica con el chequeo 13: **toda description tiene que
nombrar al menos otra skill del repo**. Es un desambiguador barato y, a diferencia de la
prosa, se puede comprobar.

El costo medido: las 15 descriptions pasan de 2.939 a ~4.300 caracteres, unos 350 tokens
por sesión. Se pagan en cada sesión y compran que el agente no cargue cinco skills para
una feature.

### Por qué `grilling` → `fleet-interview`

El original (`grill-me`) es un puntero de 157 bytes que invoca la skill `grilling`. Aquí se
instala la skill con la lógica real y se le da un nombre propio (`fleet-interview`), para que
instalar `npx skills add mattpocock/skills` más adelante no deje dos skills con el mismo nombre
compitiendo en el mismo agente.

Si preferís el nombre original, renombrá el directorio y el campo `name` del frontmatter.

### Por qué `backlog`, `story` y `pair` → `fleet-backlog`, `fleet-story` y `fleet-pair`

Mismo motivo que con `grilling`: `backlog`, `story` y `pair` son nombres genéricos que
colisionarian con cualquier otro set de skills instalado en la misma máquina. El prefijo
`fleet-` los deja en la familia y no compiten.

### `nschurmann/hola-ai`: el loop que faltaba en la cadena

El upstream (`hola-ai`, MIT) publica tres skills que cubren el tramo de la cadena que
este repo no tenía: **partir una idea en historias verticales, refinar una, y escribir
el código en pasos testeados**. Antes de esto, la cadena saltaba de la fase 1 (diseño)
a la fase 4 (commit) sin una skill que dijera cómo se escribe el código.

Las tres se adapteon al contrato del repo, y las diferencias con el upstream son
deliberadas:

| Upstream | acá | Por qué |
|---|---|---|
| `backlog` escribe en `CLAUDE.md` | `AGENTS.md` | El repo usa `AGENTS.md` como contrato. |
| `story` no nombra el tracker | el tracker es del usuario: GitHub Issues, Jira, Trello, o un `backlog.md` | El upstream exige un tracker configurado; esta versión funciona sin uno. |
| `pair` dice "Never commit" | propone el mensaje y commitea siguiendo `work-unit-commits` | En este repo el agente commitea, con la aprobación del humano. El commit sigue siendo un checkpoint. |
| `pair` sugiere `/code-review` | aplica `verification-before-completion` | El repo no tiene `code-review` (está en el roadmap) y sí tiene la puerta de verificación. |
| `pair` no menciona el orden del test en el diff | "el test va antes que la implementacion" | Es la forma de detectar al agente que toca los tests para que pasen. La regla también quedó en `work-unit-commits`, y `scripts/check-skills.py` verifica que no se venza en uno de los dos lados. |

El `disable-model-invocation: true` del upstream se conserva: las tres arrancan un flujo
con checkpoints humanos y el agente no debe dispararlas solo.

## Auditoría 2026-10-20

Cambios aplicados sobre las nueve skills. Se registran acá porque la regla 1 del repo
exige que toda edicion a una skill derivada de upstream quede anotada con su licencia.

### Frontmatter

Todos los `SKILL.md` quedan con el mismo esquema minimo: `name`, `description`, `license`,
`version`. Antes havia tres generaciones distintas y tres skills sin `license`, que es
justo el campo que la licencia exige conservar. `scripts/check-skills.py` lo verifica.

### Contenido duplicado que habia derivado

| Que estaba duplicado | Como se resolvio |
|---|---|
| El prompt de review estaba en `SKILL.md` (Step 3), en `prompts/review.md` y en un fallback dentro de `review-call.js`, con tres textos distintos | `prompts/review.md` es la fuente de verdad. `SKILL.md` lo referencia. El fallback del JS ahora falla con un error claro en vez de enviar un prompt improvisado |
| El prompt de auto-fix estaba en `SKILL.md` (Step 4, en prosa) y en `prompts/auto-fix.md` (con el contrato JSON) | Mismo criterio: `prompts/auto-fix.md` manda, `SKILL.md` lo referencia |
| La deteccion de stack estaba en la tabla de `SKILL.md` y en un bloque bash que era una copia de `scripts/run.sh`, ya divergida | `scripts/run.sh` es la unica implementacion. `SKILL.md` Step 1 documenta que corre; Step 2 lo invoca |
| La regex de `.env` estaba en `run.sh`, en `examples/pre-push.sh` y en `SKILL.md`, con dos patrones | Un solo patron canonico, verificado en los tres lugares por `scripts/check-skills.py` |

### Correcciones de contenido

- `fleet-conventions`: la description decia "Generado desde el vault" cuando la skill es
  curada a mano. Ahora dice "Curado a mano desde el vault".
- `fleet-interview`: la description disparaba solo ante "grill", en conflicto con
  `AGENTS.md`, que la pide "antes de implementar algo no trivial". Ahora cubre ambos
  triggers.
- `session-handoff`: el bloque de codigo del template estaba truncado al renderizar: el
  fence anidado de bash cerraba antes el fence contenedor de markdown, y las secciones 4 y
  5 quedaban fuera de la plantilla. Corregido con un fence externo de 4 backticks.
- `work-unit-commits`: eliminada la jerga del framework ODD. Se conserva lo exigible
  (umbral de 400 lineas, evidencia de tests, limite de rollback).
- `pre-push-qa`: `metadata.related` apuntaba a skills que no viven en este repo; ahora
  esa seccion aclara que son opcionales y externas. El bloque de instalacion usaba
  `rm -rf`, contrario a la linea roja del repo: ahora usa `gio trash`.

### El orden de las skills

Se creo `skills/fleet-conventions/CHAIN.md` como fuente de verdad del orden, por fases.
A cada `SKILL.md` se le agrego una seccion "En la cadena" con su fase, y
`scripts/check-skills.py` verifica que CHAIN.md y los `SKILL.md` no se contradigan.

El orden anterior vivia solo en un diagrama de README que ningun agente lee en runtime.
Ademas estaba mal: `systematic-debugging` figuraba despues de `pre-push-qa` (pero un
bug de logica aparece durante la implementacion, y el gate solo ve lint, tipos y tests),
`cognitive-doc-design` figuraba despues de `session-handoff` (el cuerpo de un PR se
escribe antes del push) y `fleet-conventions` y `domain-modeling` no aparecian.

### Lo que no se toco

- `cognitive-doc-design` y `verification-before-completion`: el cuerpo queda intacto.
- La cadena de skills (que skill sigue a cual) no cambia: sigue siendo la del `README.md`.

## Licencias upstream completas

- **MIT** — `pre-push-qa`, `verification-before-completion`, `systematic-debugging`,
  `domain-modeling`, `fleet-interview`, `fleet-backlog`, `fleet-story`, `fleet-pair`
- **Apache-2.0** — `work-unit-commits`, `cognitive-doc-design`

El texto completo de cada licencia está en [`LICENSES/`](../LICENSES/):
`LICENSES/MIT-obra-superpowers.txt`, `LICENSES/MIT-mattpocock.txt`,
`LICENSES/MIT-nschurmann-hola-ai.txt`,
`LICENSES/Apache-2.0-gentleman-programming.txt`.

## Cómo actualizar una skill desde upstream

1. Descargar el `SKILL.md` nuevo del repo de origen.
2. Comparar con la copia local (`diff`).
3. Aplicar los cambios upstream **más** los ajustes de esta tabla.
4. Actualizar la fecha de sincronización en este archivo.
5. `python3 scripts/sync-conventions.py --check` si tocaste `fleet-conventions`.

Los archivos de skills upstream son MIT o Apache-2.0: ambos permiten este uso y ambos
exigen conservar el aviso de licencia.

## Skills consideradas y descartadas

| Skill | Motivo |
|---|---|
| `obra/superpowers` (set completo) | 14 skills + plugin por cada harness. En Hermes no hay post-compaction hook, así que una sesión larga pierde el bootstrap. Se tomaron solo las piezas con lógica propia y sin dependencias. |
| `mattpocock/skills`: `to-spec`, `to-tickets`, `code-review` | Dependen de `/setup-matt-pocock-skills` y de un issue tracker configurado. Forkearlas arrastra infraestructura que este repo no tiene. Quedan declaradas en el roadmap. |
| `mattpocock/skills`: `grill-me`, `implement` | Punteros de <700 bytes que delegan a otras skills. Forkear un puntero sin su destino lo deja roto. |
| `Gentleman-Skills` (24 skills) | Todas de framework (electron, java-21, spring-boot-3, zod-4, tailwind-4). Dominio, no estructura de trabajo. |
| `gentle-ai` review tools (`gentle_review_*`) | No son `SKILL.md`: viven dentro del binario Go. No son forkables. Además `gentle-ai install --agent hermes` sobrescribe `AGENTS.md` y `CLAUDE.md` de los perfiles. |
| `gentle-ai`: `comment-writer` | Reglas de GitHub y voseo que no son las de este fleet. |
| `gentle-ai`: `chained-pr`, `rdd-*`, `branch-pr` | Dependen de issue tracker y de la infraestructura RDD interna (`internal/assets/`), no accesible. |

## Análisis de portabilidad de `gentle-ai`

Verificado leyendo los 3 repos (`gentle-ai`, `gentle-pi`, `Gentleman-Skills`).

**Portable — `SKILL.md` autocontenido:** `work-unit-commits`, `cognitive-doc-design`. Cero
dependencias, sin pointers. `issue-root-resolution` y `systemic-issue-triage` son portables
en método pero referencian `internal/assets/` (no público).

**No portable — el review path "4R / JD / lens":** no es un `SKILL.md`. Es tooling
`gentle_review_*` compilado dentro del binario Go de `gentle-ai`, así que no se puede leer,
forkear ni ejecutar sin Go. No decir que "esa disciplina está en Pi y no disponible en otros
agentes": decir que el binario la implementa y que estas skills son la forma portable más
cercana.

**Las skills declaran Apache-2.0 aunque el repo sea MIT.** Por eso este repo lleva `NOTICE`
y `LICENSES/`.

**`Gentleman-Skills` no sirve para esto:** las 24 entradas son guías de framework/SDK
(electron, java-21, spring-boot-3, zod-4, tailwind-4), no estructura de trabajo. No leer el
nombre de la organización como evidencia de que todo su repo vale la pena minar.

**Ojo con el instalador:** `gentle-ai install --agent hermes` sobrescribe `AGENTS.md`,
`CLAUDE.md` y mergea MCP configs de los perfiles. Con configuración propia, eso es
destructivo. Siempre `--dry-run` primero, y nunca apuntarlo a un perfil con reglas propias.