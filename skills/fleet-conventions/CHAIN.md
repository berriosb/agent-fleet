# La cadena de skills

Orden canónico del fleet. Una sola fuente de verdad: cada `SKILL.md` declara en qué
fase entra, y `scripts/check-skills.py` verifica que este archivo y los `SKILL.md` no se
contradigan. Si tocás una skill, tocás también acá.

## Por qué fases y no una lista

Porque no todos los pasos son secuenciales. Hay skills transversales (se cargan una vez y
rigen todo), condicionales (se disparan ante un evento) y repetibles (se usan cada vez que
ocurre algo). Un diagrama lineal miente sobre esas tres cosas.

Una fase es un momento del trabajo. Cada skill pertenece a al menos una.

## Las fases

| Fase | Nombre | Skill | Se carga cuando |
|---|---|---|---|
| 0 | Base | `fleet-conventions` | Siempre, antes de cualquier otra cosa. Reglas transversales. |
| 0 | Base | `hermes-agent` | Se configura, extiende, depura o audita Hermes mismo: el guia de operacion del vehiculo. |
| 1 | Diseño | `fleet-interview` | La tarea no es trivial o tiene decisiones abiertas. |
| 1 | Diseño | `fleet-backlog` | Se parte una idea en historias de usuario. Explícita. |
| 1 | Diseño | `fleet-story` | Se refina UNA historia: criterios de aceptación y out of scope. Explícita. |
| 1 | Diseño | `work-unit-commits` | Para partir el trabajo en commits antes de implementar. |
| 1 | Diseño | `domain-modeling` | Una decisión cambió el vocabulario, o va un ADR. |
| 2 | Implementación | `fleet-pair` | Se implementa una historia refinada, en pasos testeados. Explícita. |
| 2 | Implementación | `systematic-debugging` | Apareció un bug, un test falla, algo se comporta raro. |
| 2 | Implementación | `cognitive-doc-design` | Escribís un doc, un README, una nota de arquitectura. |
| 3 | Verificación | `verification-before-completion` | Antes de afirmar que algo está terminado, y antes de commitear. |
| 3 | Verificación | `pre-push-qa` | Los chequeos de lint, tipos y tests. Por commit, con `--scope static`; completo, antes del push. |
| 3 | Verificación | `hermes-profile-audit` | Se audita el estado de un perfil del fleet: antes o después de un `hermes update`, cuando un perfil se comporta mal, o en un barrido periodico. |
| 3 | Verificación | `hermes-fleet-audit` | Se audita el fleet completo: inventario de skills por perfil, drift, uso real, memoria y plugins. |
| 4 | Commit | `fleet-pair` | Cierra cada unidad de trabajo: el gate de la fase 3 primero, el commit después. Explícita. |
| 4 | Commit | `work-unit-commits` | Antes de cada `git commit`: qué va en este commit y con qué mensaje. |
| 5 | Push | `pre-push-qa` | El marcador de verificación, que se genera **después** del commit. |
| 5 | Push | `cognitive-doc-design` | Escribís el cuerpo del PR. |
| 6 | Cierre | `session-handoff` | Cerrás sesión, compactás contexto o traspasás la tarea. |

Tres de las skills se invocan **explícitamente**: `fleet-backlog`, `fleet-story` y
`fleet-pair`. Arrancan un flujo con checkpoints humanos, así que lo natural es pedirlas
por nombre. En Claude Code eso está garantizado por `disable-model-invocation: true`; en
el resto de los agentes ese campo se ignora (no es parte del estándar Agent Skills) y
lo que las apaga es el texto `Trigger: ...` de su `description`.

## El modelo por fase

El modelo que rinde en una fase no es el mismo que en otra. Esta tabla es una guía,
no una regla: lo que no se negocia es la razón de cada fila.

| Fase | Modelo | Por qué |
|---|---|---|
| 0 · Base | El que sea | Leer reglas transversales no cuesta tokens de razonamiento. |
| 1 · Diseño | El más capaz que tengas disponible | Razonar sobre alcance, requisitos y criterios de aceptación no tolera un modelo flojo. Acá el costo se paga una vez. |
| 2 · Implementación | El más rápido que siga siendo bueno | El loop es test → código mínimo → verde. La latencia se paga en cada iteración, y son muchas. |
| 3 · Verificación | El que sea: son comandos, no razonamiento | Correr lint, tipos y tests no necesita un modelo. |
| 4 · Commit | El que sea | El mensaje se decide con `work-unit-commits`. |
| 5 · Push | El más capaz, una sola vez | El cuerpo del PR y el review es donde el modelo caro rinde. |
| 6 · Cierre | El que sea | Volcar el estado a disco no requiere criterio. |

## Seis reglas que el orden no puede capturar

**1. `verification-before-completion` es una puerta, no un paso.** Se dispara en cada
afirmación de éxito, no una vez al final: antes de commitear, antes de pasar a la tarea
siguiente, antes de delegar. Su phase es 3, pero su alcance es transversal.

**2. `pre-push-qa` tiene dos momentos.** Los chequeos (lint, tipos, tests) pertenecen a
la fase 3. El **marcador** pertenece a la fase 5 y se genera **después** del commit: el hook
compara el hash del marcador contra el HEAD exacto que se está por pushear. Si el QA se
corre antes del commit, el marcador queda viejo y el push se bloquea con
`STALE MARKER ERROR`. Ver el *CRITICAL TIMING NOTE* del Step 5 de la skill.

**3. `systematic-debugging` no espera al push.** Se dispara durante la implementación, en
cualquier momento. El gate de `pre-push-qa` solo ve lint, tipos y tests: un bug de lógica
nunca llega ahí. Si el bug aparece antes del commit, se depura antes del commit.

**4. `fleet-interview` y `fleet-backlog` no son lo mismo.** `fleet-interview` interroga el
árbol de decisiones de una tarea: son las decisiones abiertas de lo que hay que construir.
`fleet-backlog` parte una idea en historias de usuario; `fleet-story` refina **una** de
ellas. Cuando la tarea es una historia sola, `fleet-story` alcanza y `fleet-interview`
sobra. Cuando la tarea es un sistema entero, `fleet-backlog` va primero y `fleet-interview`
decide lo que las historias no alcanzan a decidir.

**5. El loop 2 → 3 → 4 se repite por unidad de trabajo.** `fleet-pair` escribe el código
(fase 2), el gate corre **antes de cada commit** (fase 3, con `--scope static`: lint,
tipos y build) y recién después se commitea (fase 4). **Ningún commit entra al historial
sin haber pasado el gate.** El gate completo —con la suite entera— corre una sola vez,
antes del push, y es el que escribe el marcador de la fase 5.

Esto es lo que hace que la fase 3 preceda a la fase 4 sin contradecirse: no es "el gate
una vez y después todos los commits", es "el gate en cada commit". El orden de las fases
es el de una repetición, no el de una lista lineal.

**6. El skip de `pre-push-qa` es local.** "Just commit" / "skip review" apagan el review
con IA y el auto-fix. El gate entero se saltea con diff de documentación, con un repo
sandbox, o si el usuario lo pide — y en ese último caso se dice en voz alta que el push
fue sin verificar. **Nunca apagan `verification-before-completion`**: es otra skill, en
otra fase, y es la evidencia de cada afirmación. Si el gate se salteó, no se puede decir
"los tests pasan": se dice "el gate se salteó a pedido del usuario" y la afirmación queda
sin hacer.

## Qué NO define este orden

- Qué pasos se saltan. Una tarea trivial no necesita `fleet-interview` ni
  `work-unit-commits`.
- Cómo se delega. Un subagente puede cumplir varias fases en su propio contexto; lo que
  no puede es declarar terminado sin evidencia.
- El orden interno de un commit. Lo define `work-unit-commits`, no este archivo.
