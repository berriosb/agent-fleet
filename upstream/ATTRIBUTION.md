# Attribution

Este repo mezcla material propio con skills adaptadas de terceros. Cada skill conserva la
licencia de su origen. Los avisos exigidos por Apache-2.0 están en `NOTICE`.

## Skills propias

| Skill | Autor | Licencia |
|---|---|---|
| `fleet-conventions` | Bastián Berrios | MIT |

## Skills adaptadas

| Skill | Origen | Licencia | Cambios |
|---|---|---|---|
| `pre-push-qa` | [`berriosb/pre-push-qa`](https://github.com/berriosb/pre-push-qa) | MIT | developing |
| `verification-before-completion` | [`obra/superpowers`](https://github.com/obra/superpowers) `skills/verification-before-completion` | MIT | Copy literal. Sin cambios. |
| `domain-modeling` | [`mattpocock/skills`](https://github.com/mattpocock/skills) `skills/engineering/domain-modeling` | MIT | Copy literal. Sin cambios. |
| `fleet-interview` | [`mattpocock/skills`](https://github.com/mattpocock/skills) `skills/productivity/grilling` | MIT | Copy literal. Renombrada de `grilling` para no colisionar con el original upstream. Ver nota abajo. |
| `work-unit-commits` | [`Gentleman-Programming/gentle-ai`](https://github.com/Gentleman-Programming/gentle-ai) `skills/work-unit-commits` | Apache-2.0 | Copy literal. Sin cambios. |
| `cognitive-doc-design` | [`Gentleman-Programming/gentle-ai`](https://github.com/Gentleman-Programming/gentle-ai) `skills/cognitive-doc-design` | Apache-2.0 | Copy literal. Sin cambios. |

### Por qué `grilling` → `fleet-interview`

El original (`grill-me`) es un puntero de 157 bytes que invoca la skill `grilling`. Aquí se
instala la skill con la lógica real y se le da un nombre propio, para que instalar
`npx skills add mattpocock/skills` más adelante no deje dos skills con el mismo nombre
compitiendo en el mismo agente.

Si preferís el nombre original, renombrá el directorio y el campo `name` del frontmatter.

## Licencias upstream completas

- **MIT** — `pre-push-qa`, `verification-before-completion`, `domain-modeling`,
  `fleet-interview`
- **Apache-2.0** — `work-unit-commits`, `cognitive-doc-design`

El texto completo de ambas licencias está en [`LICENSES/`](LICENSES/):
`LICENSES/MIT-obra-superpowers.txt`, `LICENSES/MIT-mattpocock.txt`,
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