# agent-fleet

Contrato de trabajo para los agentes. `AGENTS.md` es lo primero que lee cualquier
AGENTS.md-aware agent (Codex, Cursor, Copilot, Gemini CLI, Aider, Zed) al abrir el repo, y
por tanto **el único sitio donde una regla se carga sin depender de que el agente "se
acuerde"** de buscarla.

## Skills de este repo

| Skill | Cuándo |
|---|---|
| `fleet-conventions` | **Siempre.** Las reglas universales. Leer antes de empezar cualquier tarea. |
| `fleet-interview` | Antes de implementar algo no trivial o con decisiones abiertas. |
| `work-unit-commits` | Antes de cada commit. |
| `pre-push-qa` | Antes de cada `git push` o `gh pr create`. |
| `verification-before-completion` | Antes de declarar algo terminado. |
| `domain-modeling` | Al cambiar vocabulario del dominio o escribir un ADR. |
| `cognitive-doc-design` | Al escribir docs, README, PRs o architecture notes. |

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

## Verificación

```bash
# Skills bien formadas y referenciadas
python3 scripts/sync-conventions.py --check

# Runner de QA sobre este repo (docs-only: se salta lint de código)
./skills/pre-push-qa/scripts/run.sh
```

## Licencia

MIT. Las skills adaptadas conservan su licencia original (MIT y Apache-2.0). Ver `NOTICE` y
`upstream/ATTRIBUTION.md`.