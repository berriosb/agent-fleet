# agent-fleet

Contrato de trabajo para los agentes. `AGENTS.md` es lo primero que lee cualquier
AGENTS.md-aware agent (Codex, Cursor, Copilot, Gemini CLI, Aider, Zed) al abrir el repo, y
por tanto **el único sitio donde una regla se carga sin depender de que el agente "se
acuerde"** de buscarla.

## Skills de este repo

El orden canónico vive en
[`skills/fleet-conventions/CHAIN.md`](skills/fleet-conventions/CHAIN.md). Cada skill
declara su fase en su propia sección "En la cadena", y `scripts/check-skills.py`
verifica que ambas cosas coincidan: el orden no puede quedar solo en un diagrama.

| Fase | Skill | Cuándo |
|---|---|---|
| 0 · Base | `fleet-conventions` | **Siempre.** Las reglas universales. Leer antes de empezar cualquier tarea. |
| 1 · Diseño | `fleet-interview` | Antes de implementar algo no trivial o con decisiones abiertas. |
| 1 · Diseño | `work-unit-commits` | Para partir el trabajo en commits antes de implementar. |
| 1 · Diseño | `domain-modeling` | Al cambiar vocabulario del dominio o escribir un ADR. |
| 2 · Implementación | `systematic-debugging` | Ante cualquier bug, fallo de test o error inesperado (investigar causa raíz antes de parchar). |
| 2 · Implementación | `cognitive-doc-design` | Al escribir docs, README o notas de arquitectura. |
| 3 · Verificación | `verification-before-completion` | Antes de declarar algo terminado, y antes de commitear. |
| 3 · Verificación | `pre-push-qa` | Los chequeos de lint, tipos y tests. |
| 4 · Commit | `work-unit-commits` | Antes de cada commit. |
| 5 · Push | `pre-push-qa` | Antes de cada `git push` o `gh pr create`. El marcador se genera **después** del commit. |
| 5 · Push | `cognitive-doc-design` | Al escribir el cuerpo de un PR. |
| 6 · Cierre | `session-handoff` | Al cerrar sesión, antes de compactar contexto o al traspasar trabajo a otro agente. |

Tres cosas que el orden no captura y conviene saber:

- `verification-before-completion` es una **puerta**, no un paso: se dispara en cada
  afirmación de éxito, no una vez al final.
- `pre-push-qa` tiene **dos momentos**: los chequeos en la fase 3, el marcador en la
  fase 5 y **después** del commit. Si el QA corre antes del commit, el push se bloquea
  con `STALE MARKER ERROR`.
- `systematic-debugging` **no espera al push**: el gate solo ve lint, tipos y tests, no
  bugs de lógica.

Instalación global (todos los agentes de la máquina):

```bash
npx skills add berriosb/agent-fleet -g
```

## Reglas de este repo

1. **No se edita una skill upstream sin actualizar `upstream/ATTRIBUTION.md`.** La licencia
   es parte del archivo.
2. **`fleet-conventions/SKILL.md` se cura a mano; `references/vault-conventions.md` se
   regenera.** Nunca al revés. Ver `scripts/sync-conventions.py`.
3. **Una skill = una responsabilidad.** Si el nombre necesita una "y", probablemente son
   dos skills.
4. **Sin deps externas en los scripts.** `scripts/` solo usa stdlib, para que funcione en
   cualquier agente sin instalar nada.
5. **Cero glifos CJK en cualquier archivo escrito.** Correr el chequeo antes de commitear.
   Ver la sección de `fleet-conventions`.
6. **Una skill que no está enlazada no existe.** Si agregás una skill al repo, enlazala
   en los directorios de agente: `python3 scripts/check-install.py` te dice qué falta.

## Verificación

```bash
# Verificación del repo. Hermética: no depende de tu máquina. Es lo que corre la CI.
./scripts/verify.sh
```

Los cuatro pasos, por separado:

```bash
python3 scripts/sync-conventions.py --check  # la referencia proyecta igual al vault
python3 scripts/check-skills.py              # frontmatter, CJK, fences, flags, cadena
bash scripts/verify-hook.sh                  # el hook acepta, consume y bloquea bien
./skills/pre-push-qa/scripts/run.sh         # el gate pasa sobre el repo
```

El estado de **tu máquina** (las skills enlazadas donde los agentes las buscan) es otra
verificación, no del repo. Por eso va aparte:

```bash
python3 scripts/check-install.py             # o: ./scripts/verify.sh --install
```

Los tres primeros también corren en CI (`.github/workflows/validate.yml`), contra los
mismos scripts: local y remoto aplican exactamente los mismos criterios.

## Instalación en la máquina

```bash
# Enlaza todas las skills en todos los directorios de agente
SRC="$HOME/Proyectos/agent-fleet/skills"
for dest in "$HOME/.agents/skills" "$HOME/.claude/skills" \
            "$HOME/.codex/skills" "$HOME/.gemini/skills"; do
  mkdir -p "$dest"
  for skill in "$SRC"/*/; do
    ln -sfn "$skill" "$dest/$(basename "$skill")"
  done
done
```

`scripts/check-install.py` verifica que no falte ninguna y que no queden copias
divergentes en los perfiles de Hermes.

## Licencia

MIT. Las skills adaptadas conservan su licencia original (MIT y Apache-2.0). Ver `NOTICE` y
`upstream/ATTRIBUTION.md`.