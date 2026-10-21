#!/usr/bin/env python3
"""
check-install.py — verifica que las skills del repo esten enlazadas donde los agentes
las buscan, y que no queden copias divididas que derivan en silencio. Solo stdlib.

Por que existe
──────────────
`AGENTS.md` promete nueve skills. El repo las contiene todas, pero un agente solo ve
las que estan enlazadas en su directorio de skills. Una skill que existe en el repo y
no esta enlazada no existe para ningun agente, y no hay ninguna señal: el agente
simplemente no la carga.

Este chequeo cierra ese hueco. Es la unica forma de que "la cadena" sea real en vez de
un diagrama.

Que hace
────────
1. Directorios REQUERIDOS (~/.agents, ~/.claude, ~/.codex, ~/.gemini): todas las skills
   del repo deben estar enlazadas. Son los destinos que documenta el propio repo.
2. Perfiles Hermes: no se exige la presencia de las skills (cada perfil tiene su propio
   curado), pero si una skill con NUESTRO nombre aparece ahi como copia independiente en
   vez de enlace, se reporta: dos copias del mismo nombre divergen sin avisar.

Si no existe ningun directorio de agente (por ejemplo en CI), sale con 0: no hay nada
que verificar y no hay nada que fallar.

Uso
───
    python3 scripts/check-install.py            # exit 1 si falta algun enlace
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"

# Destinos donde el repo exige que esten TODAS las skills.
REQUIRED_ROOTS = [
    "~/.agents/skills",
    "~/.claude/skills",
    "~/.codex/skills",
    "~/.gemini/skills",
]

# Directorios de skills por perfil de Hermes. Ahi no se exige presencia: solo se
# detectan copias divididas de skills que tambien viven en este repo.
HERMES_SKILL_GLOBS = [
    "~/.hermes/profiles/*/skills/*",
]


def expand(pattern: str) -> list[Path]:
    """Expande un patron con uno o varios `*`. Devuelve solo lo que existe en disco."""
    path = Path(pattern).expanduser()
    parts = path.parts
    if parts and parts[0] == "/":
        current = [Path("/")]
        rest = parts[1:]
    else:
        current = [Path(".")]
        rest = parts

    for part in rest:
        if "*" in part:
            nxt: list[Path] = []
            for base in current:
                try:
                    nxt.extend(sorted(m for m in base.glob(part) if m.is_dir()))
                except OSError:
                    continue
            current = nxt
        else:
            current = [base / part for base in current]

    return [c for c in current if c.is_dir()]


def resolves_into_repo(path: Path) -> bool:
    """True si el enlace termina dentro de skills/ de este repo."""
    try:
        target = Path(os.path.realpath(path))
    except OSError:
        return False
    try:
        target.relative_to(SKILLS_DIR.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="solo el resumen")
    args = parser.parse_args()

    skills = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    if not skills:
        print("ERROR: no se encontraron skills en skills/*/", file=sys.stderr)
        return 1

    problems: list[str] = []
    checked_roots = 0

    # 1. Raices requeridas: todas las skills deben estar enlazadas.
    for pattern in REQUIRED_ROOTS:
        root = Path(pattern).expanduser()
        if not root.is_dir():
            continue
        checked_roots += 1
        for skill in skills:
            link = root / skill
            if not link.exists() and not link.is_symlink():
                problems.append(f"FALTA: {link}")
            elif not link.is_symlink():
                problems.append(f"ROTO: {link} — existe pero no es un enlace simbolico")
            elif not resolves_into_repo(link):
                problems.append(f"ROTO: {link} — el enlace no apunta a este repo")

    # 2. Perfiles Hermes: copiar es una copia divergente esperando a pasar.
    hermes_dirs: list[Path] = []
    for pattern in HERMES_SKILL_GLOBS:
        hermes_dirs.extend(expand(pattern))
    for category in hermes_dirs:
        for skill in skills:
            candidate = category / skill
            if not candidate.exists():
                continue
            if candidate.is_symlink() and resolves_into_repo(candidate):
                continue
            problems.append(
                f"DIVERGENTE: {candidate} — copia independiente de una skill de este repo; "
                "va a derivar sin avisar. Enlazalo al repo o sacalo del perfil."
            )

    if not checked_roots and not hermes_dirs:
        print("OK: no hay directorios de skills de agente en esta maquina; nada que verificar.")
        return 0

    if problems:
        for message in problems:
            print(message, file=sys.stderr)
        print("", file=sys.stderr)
        print("Para enlazar todo en los directorios requeridos:", file=sys.stderr)
        print(
            '  SRC="$HOME/Proyectos/agent-fleet/skills"\n'
            '  for dest in "$HOME/.agents/skills" "$HOME/.claude/skills" \\\n'
            '             "$HOME/.codex/skills" "$HOME/.gemini/skills"; do\n'
            '    mkdir -p "$dest"\n'
            '    for skill in "$SRC"/*/; do\n'
            '      ln -sfn "$skill" "$dest/$(basename "$skill")"\n'
            "    done\n"
            "  done",
            file=sys.stderr,
        )
        print(f"\n{len(problems)} problema(s).", file=sys.stderr)
        return 1

    print(
        f"OK: {len(skills)} skills enlazadas en {checked_roots} directorios de agente; "
        f"{len(hermes_dirs)} directorios de perfil Hermes revisados."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
