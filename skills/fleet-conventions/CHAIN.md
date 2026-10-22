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
| 1 | Diseño | `work-unit-commits` | Para partir el trabajo en commits antes de implementar. |
| 1 | Diseño | `domain-modeling` | Una decisión cambió el vocabulario, o va un ADR. |
| 2 | Implementación | `systematic-debugging` | Apareció un bug, un test falla, algo se comporta raro. |
| 2 | Implementación | `cognitive-doc-design` | Escribís un doc, un README, una nota de arquitectura. |
| 3 | Verificación | `verification-before-completion` | Antes de afirmar que algo está terminado, y antes de commitear. |
| 3 | Verificación | `pre-push-qa` | Los chequeos de lint, tipos y tests. |
| 3 | Verificación | `hermes-profile-audit` | Se audita el estado de un perfil del fleet: antes o después de un `hermes update`, cuando un perfil se comporta mal, o en un barrido periodico. |
| 3 | Verificación | `hermes-fleet-audit` | Se audita el fleet completo: inventario de skills por perfil, drift, uso real, memoria y plugins. |
| 4 | Commit | `work-unit-commits` | Antes de cada `git commit`: qué va en este commit. |
| 5 | Push | `pre-push-qa` | El marcador de verificación, que se genera **después** del commit. |
| 5 | Push | `cognitive-doc-design` | Escribís el cuerpo del PR. |
| 6 | Cierre | `session-handoff` | Cerrás sesión, compactás contexto o traspasás la tarea. |

## Tres reglas que el orden no puede capturar

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

## Qué NO define este orden

- Qué pasos se saltan. Una tarea trivial no necesita `fleet-interview` ni
  `work-unit-commits`.
- Cómo se delega. Un subagente puede cumplir varias fases en su propio contexto; lo que
  no puede es declarar terminado sin evidencia.
- El orden interno de un commit. Lo define `work-unit-commits`, no este archivo.
