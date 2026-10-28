"""
sync-conventions.py — regenera skills/fleet-conventions/references/vault-conventions.md
desde el vault.

Por qué existe
──────────────
`Agent-Shared/conventions.md` en el vault es la fuente de verdad de las reglas del fleet.
`skills/fleet-conventions/references/vault-conventions.md` es la proyección legible del
vault, para agentes que no abren el vault.

`SKILL.md` NO se regenera: es una skill curada a mano, y el vault todavía no cubre todo lo
que el fleet necesita (la regla CJK y el borrado recuperable viven en `lessons-learned.md` y
en la memoria del perfil, no en `conventions.md`). Regenerarlo perdería esas reglas.

Por eso el sync es de una sola dirección y escribe en `references/`: el vault se proyecta
sin sobrescribir la curation. `SKILL.md` enlaza a la referencia para el detalle literal.

Render determinista
───────────────────
El archivo generado se compara byte a byte contra el vault, así que el render NO puede
contener valores volátiles (la fecha del día, la ruta local absoluta). Todo lo que cambia
cuando cambia el vault está en `metadata.hermes.source_sha256`; mientras el vault no cambie,
el sha no cambia y el archivo tampoco.

Por eso el `name` y la `description` se COPIAN del `SKILL.md` curado: hay una sola fuente
de verdad para el frontmatter y no puede derivar. `scripts/check-skills.py` lo verifica.

Multi-fuente
────────────
El vault se puede leer desde el disco local y/o desde el mirror remoto. Si ambos son
alcanzables pero dicen cosas distintas, el mirror está desactualizado: se reporta como
conflicto explícito en vez de fallar en silencio.

Uso
───
    python3 scripts/sync-conventions.py              # verifica y escribe si cambió
    python3 scripts/sync-conventions.py --check      # solo compara (para CI, exit 1 si difiere)

Depende de: python3 stdlib. Sin dependencias externas.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CURATED = REPO / "skills" / "fleet-conventions" / "SKILL.md"
TARGET = REPO / "skills" / "fleet-conventions" / "references" / "vault-conventions.md"

VAULT_REL = "Agent-Shared/conventions.md"
VAULT_PATHS = [
    Path.home() / "Proyectos" / "AI" / "memorias-bastian" / VAULT_REL,
]
VAULT_URL = f"https://raw.githubusercontent.com/berriosb/memorias-bastian/main/{VAULT_REL}"

# Raices del vault en disco. El texto del vault menciona su propia ruta local,
# y esa ruta no puede viajar dentro de un archivo que se commitea y se comparte.
# El render la reemplaza por la etiqueta relativa.
VAULT_ROOTS = [
    Path.home() / "Proyectos" / "AI" / "memorias-bastian",
]

# Etiqueta estable para el texto generado. NUNCA la ruta local absoluta: el archivo se
# commitea y se comparte, y una ruta de una máquina no pertenece ahí.
VAULT_LABEL = VAULT_REL

# --------------------------------------------------------------------------------------
# Mapeo: heading del vault -> sección de fleet-conventions
#
# Las reglas del vault se agrupan por encabezado `##`. Se conservan los títulos y el
# cuerpo, más una nota al inicio sobre el alcance (todo agente, todo lenguaje), que es
# la diferencia entre el vault (Hermes) y la skill (fleet completo).
# --------------------------------------------------------------------------------------

SCOPE_NOTE = """> **Este archivo es GENERADO.** La fuente de verdad es
> `{vault}` en el vault. Para cambiar una regla: edita el vault, después corre
> `python3 scripts/sync-conventions.py` y commitea. Editar este archivo a mano se pierde
> en el próximo sync.

Estas reglas aplican a **todo agente** que trabaje con Bastián: Hermes (aura, codehak,
mingo), Claude Code, Codex, OpenCode, agy, Gemini CLI, copilot, pi, mcode. No dependen del
lenguaje ni del proyecto.
"""

# Fallback si el SKILL.md curado no está disponible. `check-skills.py` verifica que el
# archivo generado y el curado mantienen el mismo name + description.
FALLBACK_NAME = "fleet-conventions"
FALLBACK_DESCRIPTION = (
    "Reglas universales de Bastián: línea roja, idioma, verificación, borrado y entregables. "
    "Curado a mano desde el vault; aplicar en TODO trabajo, sin importar el agente o el lenguaje."
)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_curated_frontmatter() -> tuple[str, str]:
    """Lee (name, description) del SKILL.md curado. Fuente unica del frontmatter."""
    if not CURATED.is_file():
        return FALLBACK_NAME, FALLBACK_DESCRIPTION
    content = CURATED.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return FALLBACK_NAME, FALLBACK_DESCRIPTION
    fm = m.group(1)
    name = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
    desc = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
    name_val = name.group(1).strip().strip("\"'") if name else FALLBACK_NAME
    desc_val = desc.group(1).strip().strip("\"'") if desc else FALLBACK_DESCRIPTION
    return name_val, desc_val


def read_sources() -> list[tuple[str, str | None, str | None]]:
    """
    Devuelve [(etiqueta, contenido_o_None, error_o_None)] para cada fuente alcanzable.

    Todas las fuentes alcanzables se leen, no solo la primera: si el disco y el mirror
    difieren, esa diferencia es un hallazgo y se reporta.
    """
    sources: list[tuple[str, str | None, str | None]] = []

    for path in VAULT_PATHS:
        if path.is_file():
            try:
                sources.append((str(path), path.read_text(encoding="utf-8"), None))
            except OSError as exc:
                sources.append((str(path), None, str(exc)))
            break

    try:
        headers = {}
        token = os.environ.get("VAULT_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"token {token}"
        req = urllib.request.Request(VAULT_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            sources.append((VAULT_URL, response.read().decode("utf-8"), None))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        sources.append((VAULT_URL, None, str(exc)))

    return sources


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


def sanitize_local_paths(text: str) -> str:
    """Reemplaza las rutas locales del vault por la etiqueta relativa.

    Las convenciones del vault mencionan donde vive el vault. Ese archivo se
    commitea y se comparte, y una ruta de una maquina no pertenece ahi. El
    render promises que no lleva rutas locales: esto es lo que lo cumple.
    """
    for root in VAULT_ROOTS:
        text = text.replace(str(root), VAULT_REL.rsplit("/", 1)[0])
    return text


def render(sections: list[tuple[str, list[str]]], source_sha: str) -> str:
    """Construye el archivo de referencia completo."""
    name, description = read_curated_frontmatter()
    frontmatter = f"""---
name: {name}
description: "{description}"
license: MIT
metadata:
  generated: true
  source: "{VAULT_REL}"
  source_sha256: "{source_sha}"
  regenerate: "python3 scripts/sync-conventions.py"
---

# fleet-conventions

"""

    parts = [frontmatter, SCOPE_NOTE.format(vault=VAULT_LABEL), ""]

    for title, lines in sections:
        body = "\n".join(lines).strip("\n")
        if not body:
            continue
        parts.append(f"## {title}\n\n{body}\n")

    text = "\n".join(parts).rstrip("\n") + "\n"
    text = sanitize_local_paths(text)

    # Nunca reescribir con glifos CJK: si el vault trajera uno, abortar en vez de propagar.
    # El rango va en escapes: los glifos literales en el fuente serian CJK ellos mismos.
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
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
    parser.add_argument(
        "--require-vault",
        action="store_true",
        help=(
            "fallar si el vault no es accesible, en vez de omitir la comparacion. "
            "Para CI: un chequeo que no comparo no puede pasar por verde."
        ),
    )
    args = parser.parse_args()

    sources = read_sources()
    available = [(label, content) for label, content, _ in sources if content is not None]

    if not available:
        errors = "; ".join(f"{label}: {err}" for label, _, err in sources if err)
        if args.require_vault:
            sys.exit(
                f"[sync] el vault no es accesible y --require-vault esta activo: {errors}. "
                "Sin el vault no se puede verificar que la referencia este al dia, asi que "
                "el chequeo no puede pasar por verde. En CI hace falta el secret "
                "VAULT_TOKEN del repo; en local, el vault en disco."
            )
        if args.check and TARGET.is_file():
            print(
                f"[sync] AVISO: vault no accesible ({errors}). "
                f"Se omite la comparación y se preserva {TARGET.relative_to(REPO)}. "
                "Esto NO verifica nada: el paso quedo sin comparar."
            )
            return 0
        sys.exit(f"[sync] no se pudo leer el vault: {errors}")

    renders: dict[str, str] = {}
    for label, content in available:
        sections = extract_sections(content)
        if not sections:
            sys.exit(f"[sync] no se encontraron secciones `## ` en {label}")
        renders[label] = render(sections, sha256(content))

    # Conflicto entre fuentes: el disco y el mirror dicen cosas distintas.
    if len(renders) > 1 and len(set(renders.values())) > 1:
        print(
            "[sync] CONFLICTO: el vault local y el mirror remoto proyectan contenido "
            "distinto. El mirror está desactualizado o divergió.",
            file=sys.stderr,
        )
        for label in renders:
            print(f"    - {label}", file=sys.stderr)
        if args.check:
            return 1

    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.is_file() else ""
        mismatched = [label for label, rendered in renders.items() if rendered != current]
        if mismatched:
            print(
                f"[sync] DESACTUALIZADO — {TARGET.relative_to(REPO)} difiere del vault: "
                + ", ".join(mismatched)
            )
            return 1
        print(f"[sync] OK — {len(renders)} fuente(s) verificadas, sin cambios")
        return 0

    # Escritura: la fuente de verdad es el disco local; el mirror es respaldo.
    # `label` es el texto de la fuente (el path local como str, o la URL), asi
    # que se compara contra las formas str de VAULT_PATHS: comparar el str
    # contra los Path nunca da True, y la preferencia quedaba solo de casualidad.
    local_labels = {str(path) for path in VAULT_PATHS}
    preferred = next(
        (label for label, _, _ in sources if label in local_labels and label in renders),
        next(iter(renders)),
    )
    rendered = renders[preferred]
    changed = not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != rendered
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(rendered, encoding="utf-8")
    print(f"[sync] {len(renders)} fuente(s) leída(s) desde {preferred}")
    print("[sync] sin cambios" if not changed else f"[sync] escrito → {TARGET.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
