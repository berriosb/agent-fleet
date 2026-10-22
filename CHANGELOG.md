# Changelog

Registro legible de los cambios de este repo, por tema y no por versión.

El tag `v1` se mueve en cada push a `main`, así que la release es continua: no hay
versiones que numerar. Este archivo es el resumen de lo que cambió y por qué, para
poder leerlo sin bucear en el historial.

El detalle de qué se adaptó de cada upstream, y bajo qué licencia, está en
[`upstream/ATTRIBUTION.md`](upstream/ATTRIBUTION.md).

## 2026-10-22 — El fleet deja de divergir solo

Una auditoría de las skills de los cuatro perfiles de Hermes encontró que el
problema no era qué skills tenías, sino que ninguna sabía de las demás.

- **Había dos `hermes-profile-audit` con el mismo nombre y 4% de similitud.** Una en
  `codehak` (v1.0.0, 230 líneas) y otra en `mingo` (v0.1.0, 94 líneas), en categorías
  distintas. La de `mingo` era un subconjunto: le faltaban los pitfalls de plugin
  desktop-only, el contexto del engine de visión y el delta de toolsets. Ahora hay una
  sola, en `devops/`, con lo único de las dos.
- **La misma skill hacía drift entre perfiles.** `hermes-agent` tenía tres versiones
  (v2.0.0 obsoleta de 36 KB, v3.2.0 del upstream, y una tercera con las auditorías
  del fleet). La global era la vieja. Ahora `hermes-agent` es una copia exacta del
  upstream v3.2.0 más la sección "En la cadena", y las referencias que eran del
  fleet viven en su propia skill (`hermes-fleet-audit`). Así el upstream puede seguir
  actualizándola sin que se vuelva a bifurcar.
- **El mismo patrón se repitió en `systematic-debugging`, `google-workspace`,
  `youtube-content`, `grounded-citations`, `obsidian`, `github` y
  `hermes-agent-skill-authoring`.** En cada caso se compararon las versiones y se
  conservó la mejor; donde las versiones traían contenido complementario (la
  selección de llave SSH y la de *fork workflow* en `github`, el *squash merge* y el
  *branch protection* en el mismo archivo) se fusionaron en una.
- **`github` tenía tres versiones incompatibles de `pr-workflow.md`.** La de `codehak`
  tenía la sección de *squash merge*, la de `aura` la de *fork workflow*, y cada una
  numeraba sus secciones como "7". Ahora hay un archivo con las tres, numeradas.
- **`docx` en `codehak` era una versión más vieja** que el upstream (antes del
  *linter fix* que convirtió `yield from` en un loop). Restaurada.

## 2026-10-21 — El gate pasa a ser real

El repo es un quality gate para agentes, y el gate no hacía lo que prometía.

- **El typecheck de TypeScript estaba roto.** `tsc --noEmit --if-present` le pasaba a
  `tsc` un flag que es del runner de scripts (`pnpm run`), no del compilador. `tsc` lo
  rechazaba con `Unknown compiler option` y salía con código 1, así que el gate
  rechazaba **todos** los repos TypeScript. El error además estaba escondido por
  `2>/dev/null`. Ahora el typecheck corre solo si hay `tsconfig.json` y `typescript`
  instalado.
- **La CI no bloqueaba nada.** Todos los chequeos de lint terminaban en `|| true`, y los
  tests iban por `... | tail -40` sin `pipefail`: el código de salida que veía GitHub
  Actions era el de `tail`, no el del test. Una suite rota pasaba verde. Ahora la CI
  invoca el runner en vez de mantener su propia copia de los comandos, que es como
  divergía.
- **Una herramienta ausente bloqueaba el push.** Con `uv`, `uv run <tool>` cae al PATH
  y, si la herramienta tampoco está, responde `Failed to spawn` con código 2. Eso se
  tomaba por un typecheck fallido: el mismo repo pasaba en una máquina con `mypy` y
  fallaba en otra sin él. Ahora una herramienta que no está se **omite**.
- **El runner no detectaba repos Python sin manifiesto.** Caían en `mixed` y no se les
  corría nada: el gate verificaba el repo sin verificarlo.
- **La CI no ejercitaba el runner**, que es la pieza que usan los repos consumidores.
  Un fallo suyo no lo detectaba nadie.
- **La verificación del repo mezclaba dos cosas.** `verify.sh` daba el mismo resultado
  en un clone limpio y en tu máquina, y en CI no decía nada. Ahora verifica solo el
  repo, y el estado de tu máquina se comprueba aparte (`--install`).
- **El tag `v1` estaba 13 commits atrasado.** Como es lo que consumen los repos, los
  arreglos al gate no llegaban. Ahora se mueve solo en cada push a `main`, y la CI
  avisa si queda atrás.
- **Los validadores no tenían tests.** 2439 líneas de código ejecutable sin una sola
  prueba. Ahora hay 48.
- **El validador no atrapaba la clase de bug que más costó.** Un flag inválido no rompe
  nada visible: la herramienta lo rechaza y el script sigue. Ahora se verifican los
  flags prohibidos, los comandos replicados, y que la CI no reimplemente el gate.
- **`AGENTS.md` podía quedar viejo en silencio.** Es el archivo que un agente lee de
  verdad; ahora sus fases se comparan contra `CHAIN.md`.
- **Las rutas absolutas de una máquina estaban en un repo público.** Salieron las tres.
- **El tooling de QA no estaba declarado**, así que la CI corría `mypy` y el local no.
  Ahora `requirements-dev.txt` es la única declaración.
- **Go y Rust no se chequeaban.** Un repo Go caía en `mixed` y no se le corría nada.
  Ahora `go vet`/`go test` y `cargo check`/`cargo test`.
- **La instalación no cubría los cuatro roots.** `npx skills add -g` deja las skills solo
  en `~/.agents/skills/`: Claude Code, Codex y Gemini leen roots propios y quedaban
  fuera. Peor: el resultado no era lo que `check-install.py` exige, así que el repo se
  declaraba roto después de una instalación "correcta". Ahora hay `scripts/install.sh`.
- **Los tests que ya fallaban bloqueaban el push para siempre.** La skill lo prometía
  ("report them as baseline-failures... rather than blocking") y el runner no lo
  hacía. Ahora hay un baseline: un archivo con los tests que el proyecto decide
  tolerar. Solo los fallos nuevos bloquean.

## 2026-10-20 — La infraestructura de verificación

- `scripts/check-skills.py` y `scripts/check-install.py`: los validadores, en stdlib
  puro, sin dependencias externas.
- `scripts/verify-hook.sh`: round-trip del protocolo del marcador. El hook acepta un
  marcador válido, lo consume, y bloquea un marcador obsoleto o ausente.
- El sync del vault pasó a ser determinista: sin fecha ni ruta local, con el sha del
  contenido en el frontmatter. El `--check` de CI da el mismo resultado hoy y dentro de
  un mes.
- `skills/fleet-conventions/CHAIN.md` como fuente de verdad del orden de las skills, con
  la fase declarada en cada `SKILL.md` y verificada entre sí.
- La regex de `.env` unificada en los tres lugares que la replicaban, y verificada.
- `session-handoff`: el fence anidado truncaba el template y las secciones 4 y 5
  quedaban fuera de la plantilla.
