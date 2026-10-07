#!/usr/bin/env python3
"""
sync-conventions.py — regenera skills/fleet-conventions/SKILL.md desde el vault.

Por qué existe
──────────────
`Agent-Shared/conventions.md` en el vault es la fuente de verdad de las reglas del fleet.
`skills/fleet-conventions/references/vault-conventions.md` es la proyección legible del
vault, para agentes que no abren el vault.

`SKILL.md` NO se regenera: es una skill curada a mano, y el vault todavía no cubre todo lo
que el fleet necesita (la regla CJK y `gio trash` viven en `lessons-learned.md` y en la
memoria del perfil, no en `conventions.md`). Regenerarlo perdería esas reglas.

Por eso el sync es de una sola dirección y escribe en `references/`: el vault se proyecta
sin sobrescribir la curation. `SKILL.md` enlaza a la referencia para el detalle literal.

Uso
───
    python3 scripts/sync-conventions.py              # verifica y escribe si cambió
    python3 scripts/sync-conventions.py --check      # solo compara (para CI, exit 1 si difiere)

Depende de: python3 stdlib. Sin dependencias externas.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "skills" / "fleet-conventions" / "references" / "vault-conventions.md"

VAULT_REL = "Agent-Shared/conventions.md"
VAULT_PATHS = [
    Path.home() / "Proyectos" / "AI" / "memorias-bastian" / VAULT_REL,
    Path("/home/bastianberrios/Proyectos/AI/memorias-bastian") / VAULT_REL,
]
VAULT_URL = f"https://raw.githubusercontent.com/berriosb/memorias-bastian/main/{VAULT_REL}"

# --------------------------------------------------------------------------------------
# Mapeo: heading del vault -> sección de fleet-conventions
#
# Las reglas del vault se agrupan por encabezado `##`. Se conservan los títulos y el
# cuerpo, más una nota al inicio sobre el alcance (todo agente, todo lenguaje), que es
# la diferencia entre el vault (Hermes) y la skill (fleet completo).
# --------------------------------------------------------------------------------------

SCOPE_NOTE = """> **Este archivo es GENERADO.** La fuente de verdad es
> `{vault}` en el vault. Para cambiar una regla: editá el vault, después corré
> `python3 scripts/sync-conventions.py` y commiteá. Editar este archivo a mano se pierde
> en el próximo sync.

Estas reglas aplican a **todo agente** que trabaje con Bastián: Hermes (aura, codehak,
mingo), Claude Code, Codex, OpenCode, agy, Gemini CLI, copilot, pi, mcode. No dependen del
lenguaje ni del proyecto.
"""


def read_vault() -> str:
    """Devuelve el markdown del vault: archivo local si existe, si no la URL."""
    for path in VAULT_PATHS:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    try:
        with urllib.request.urlopen(VAULT_URL, timeout=20) as response:
            return response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        sys.exit(f"[sync] no se pudo leer el vault: {exc}")


def extract_sections(markdown: str) -> list[tuple[str, list[str]]]:
    """Parte el markdown en (título, líneas) por encabezado de nivel 2, sin el H1."""
    sections: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    in_code_fence = False

    for line in markdown.splitlines():
        # Un bloque de código puede contener líneas que empiezan con `##`.
        if line.lstrip().startswith("```"):
            in_code_fence = not in_code_fence
        if not in_code_fence and line.startswith("## "):
            if current_title is not None:
                sections.append((current_title, current_lines))
            current_title = line[3:].strip()
            current_lines = []
            continue
        if current_title is not None:
            current_lines.append(line)

    if current_title is not None:
        sections.append((current_title, current_lines))
    return sections


def render(sections: list[tuple[str, list[str]]], vault_label: str) -> str:
    """Construye el SKILL.md completo."""
    frontmatter = f"""---
name: fleet-conventions
description: "Reglas universales de Bastián: línea roja, idioma, verificación, borrado y entregables. Generado desde el vault; aplicar en TODO trabajo, sin importar el agente o el lenguaje."
version: 1.0.0
author: Bastián Berrios (generado desde Agent-Shared/conventions.md)
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fleet, convenciones, reglas, red-lines, espanol, verificacion]
    generated_from: "{VAULT_REL}"
    synced: {date.today().isoformat()}
    regenerate: "python3 scripts/sync-conventions.py"
---

# fleet-conventions

"""

    parts = [frontmatter, SCOPE_NOTE.format(vault=vault_label), ""]

    for title, lines in sections:
        body = "\n".join(lines).strip("\n")
        if not body:
            continue
        parts.append(f"## {title}\n\n{body}\n")

    text = "\n".join(parts).rstrip("\n") + "\n"

    # Nunca reescribir con glifos CJK: si el vault trajera uno, abortar en vez de propagar.
    cjk = re.findall(r"[一-鿿]", text)
    if cjk:
        sys.exit(f"[sync] abortado: {len(cjk)} glifos CJK en el contenido sincronizado")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="solo comparar la referencia; exit 1 si difiere del vault (para CI)",
    )
    args = parser.parse_args()

    markdown = read_vault()
    sections = extract_sections(markdown)
    if not sections:
        sys.exit("[sync] no se encontraron secciones `## ` en el vault")

    label = f"`{VAULT_REL}`"
    for path in VAULT_PATHS:
        if path.is_file():
            label = str(path)
            break
    rendered = render(sections, label)

    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
        if current == rendered:
            print(f"[sync] OK — {len(sections)} secciones, sin cambios")
            return 0
        print(f"[sync] DESACTUALIZADO — {TARGET.relative_to(REPO)} difiere del vault")
        return 1

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    changed = not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != rendered
    TARGET.write_text(rendered, encoding="utf-8")
    print(f"[sync] {len(sections)} secciones desde el vault → {TARGET.relative_to(REPO)}")
    print("[sync] sin cambios" if not changed else "[sync] escrito")
    return 0


if __name__ == "__main__":
    sys.exit(main())