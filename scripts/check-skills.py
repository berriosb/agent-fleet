#!/usr/bin/env python3
"""
check-skills.py — validacion del repo de skills. Solo stdlib.

Por que existe
──────────────
`scripts/verify.sh` y `.github/workflows/validate.yml` tenian cada uno su propio bloque
`python3 -c` con la validacion de frontmatter. Eso duplicaba la logica (y las dos
versiones ya divergian en el alcance del chequeo CJK), ademas `import yaml` rompia la
regla 4 del repo: `scripts/` solo usa stdlib.

Este modulo es la unica implementacion. `verify.sh` lo invoca; `validate.yml` tambien,
para que CI y local compartan exactamente los mismos criterios.

Chequeos
────────
1. frontmatter: cada `skills/*/SKILL.md` tiene `name`, `description`, `license`, `version`.
2. el `name` del frontmatter coincide con el nombre del directorio.
3. la referencia generada de fleet-conventions comparte `name` y `description` con el
   SKILL.md curado (no pueden derivar: el generador copia del curado).
4. CJK: cero glifos en los archivos de texto trackeados.
5. fences: ningun bloque de codigo sin cerrar, y ningun fence anidado con info string
   (un fence anidado cierra prematuramente el bloque externo y trunca el contenido).
6. la regex de deteccion de `.env` es identica en los tres lugares que la replican.
7. la cadena: CHAIN.md y cada SKILL.md declaran las mismas fases, y toda skill del repo
   aparece en la cadena. El orden no puede quedar solo en un diagrama de README.

Uso
───
    python3 scripts/check-skills.py            # exit 1 si algo falla
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"

REQUIRED_FIELDS = ("name", "description", "license", "version")

# La deteccion de archivos sensibles vive en tres lugares (el runner, el hook y el
# SKILL.md). Se declaran aqui y se comparan contra los tres: si alguien edita uno solo,
# este chequeo lo reporta.
ENV_DETECT = r"(^|/)\.env(\.[^/]*)?$"
ENV_ALLOW = r"\.(example|sample|template|test|ci|defaults)$"
ENV_PATTERN_SITES = [
    SKILLS_DIR / "pre-push-qa" / "scripts" / "run.sh",
    SKILLS_DIR / "pre-push-qa" / "examples" / "pre-push.sh",
    SKILLS_DIR / "pre-push-qa" / "SKILL.md",
]

TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".sh", ".js", ".yml", ".yaml", ".json",
    ".toml", ".cfg", ".ini", "",
}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def parse_frontmatter(path: Path) -> tuple[dict[str, str] | None, list[str]]:
    """Parsea el frontmatter de un SKILL.md. Devuelve (campos, errores)."""
    content = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not match:
        return None, ["falta el bloque de frontmatter delimitado por ---"]

    errors: list[str] = []
    fields: dict[str, str] = {}
    current: str | None = None

    for raw in match.group(1).split("\n"):
        if not raw.strip():
            continue
        if "\t" in raw:
            errors.append("el frontmatter no puede usar tabuladores para indentar")
            continue
        indented = raw[:1].isspace()
        if indented:
            # Solo se validan los niveles de primer nivel.
            if current is None:
                errors.append(f"indentación sin clave padre: {raw.strip()!r}")
            continue
        kv = re.match(r"^([A-Za-z_][A-Za-z0-9_.-]*):\s*(.*)$", raw)
        if not kv:
            errors.append(f"línea YAML inválida: {raw!r}")
            continue
        key, value = kv.group(1), kv.group(2).strip()
        current = key
        if value:
            fields[key] = value.strip("\"'")

    return fields, errors


def check_frontmatter(errors: list[str]) -> None:
    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if not skill_files:
        fail(errors, "no se encontraron skills en skills/*/SKILL.md")
        return

    for path in skill_files:
        rel = path.relative_to(REPO)
        fields, fm_errors = parse_frontmatter(path)
        for message in fm_errors:
            fail(errors, f"{rel}: {message}")
        if fields is None:
            continue

        for required in REQUIRED_FIELDS:
            if not fields.get(required):
                fail(errors, f"{rel}: falta el campo '{required}' en el frontmatter")

        dirname = path.parent.name
        if fields.get("name") and fields["name"] != dirname:
            fail(
                errors,
                f"{rel}: name '{fields['name']}' no coincide con el directorio '{dirname}'",
            )

        description = fields.get("description", "")
        if len(description) < 40:
            fail(
                errors,
                f"{rel}: description demasiado corta ({len(description)} chars); "
                "no permite al agente decidir si la skill aplica",
            )


def check_reference_drift(errors: list[str]) -> None:
    """La referencia generada debe compartir name + description con el SKILL.md curado."""
    curated = SKILLS_DIR / "fleet-conventions" / "SKILL.md"
    reference = SKILLS_DIR / "fleet-conventions" / "references" / "vault-conventions.md"
    if not reference.is_file():
        fail(errors, "falta skills/fleet-conventions/references/vault-conventions.md")
        return

    curated_fields, _ = parse_frontmatter(curated)
    reference_fields, _ = parse_frontmatter(reference)
    if not curated_fields or not reference_fields:
        fail(errors, "no se pudo leer el frontmatter de la skill curada o su referencia")
        return

    for key in ("name", "description"):
        if curated_fields.get(key) != reference_fields.get(key):
            fail(
                errors,
                f"references/vault-conventions.md: '{key}' difiere del SKILL.md curado "
                "(el generador debe copiarlo, no duplicarlo)",
            )


def check_cjk(errors: list[str]) -> None:
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.split("\0")
    except (subprocess.CalledProcessError, FileNotFoundError):
        tracked = [str(p.relative_to(REPO)) for p in REPO.rglob("*") if p.is_file()]

    checked = 0
    for rel in filter(None, tracked):
        path = REPO / rel
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        checked += 1
        glyphs = CJK_RE.findall(content)
        if glyphs:
            fail(errors, f"{rel}: {len(glyphs)} glifos CJK (usa [\\u4e00-\\u9fff])")
    if checked == 0:
        fail(errors, "el chequeo CJK no encontró ningún archivo de texto: la cobertura está rota")


def check_fences(errors: list[str]) -> None:
    """
    Detecta bloques de codigo truncados.

    Reglas CommonMark aplicadas:
    - un closer debe usar el mismo caracter y al menos tantos backticks como el que abrio
      el bloque, y no puede llevar info string;
    - por lo tanto un fence interno con el mismo largo que el externo NUNCA puede cerrarse
      solo, y ademas trunca el bloque externo: el contenido posterior queda fuera de la
      plantilla. Es el modo de falla que costo las secciones 4 y 5 de session-handoff;
    - un fence interno mas corto que el externo es contenido legitimo (ejemplo anidado).
    """
    for path in sorted(REPO.rglob("*.md")):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(REPO)
        open_len = 0
        open_line = 0
        open_lang = ""
        for lineno, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            stripped = line.lstrip()
            if not stripped.startswith("```"):
                continue
            run = len(stripped) - len(stripped.lstrip("`"))
            info = stripped[run:].strip()

            if open_len == 0:
                open_len = run
                open_line = lineno
                open_lang = info
                continue

            if run >= open_len:
                if info:
                    fail(
                        errors,
                        f"{rel}:{lineno}: fence interno de {run} backticks dentro del bloque "
                        f"de {open_len} abierto en la linea {open_line}; el bloque externo se "
                        "trunca. Usa un fence externo mas largo (````).",
                    )
                else:
                    open_len = 0
                    open_line = 0
                    open_lang = ""
            # run < open_len: es contenido legitimo del bloque abierto.

        if open_len:
            fail(
                errors,
                f"{rel}: bloque de codigo abierto en la linea {open_line} "
                f"({open_lang or 'sin lenguaje'}) nunca se cierra",
            )


def check_env_pattern(errors: list[str]) -> None:
    """La regex de .env debe ser identica en los tres sitios que la replican."""
    for path in ENV_PATTERN_SITES:
        if not path.is_file():
            fail(errors, f"falta {path.relative_to(REPO)}")
            continue
        content = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO)
        if ENV_DETECT not in content:
            fail(
                errors,
                f"{rel}: la regex de deteccion de .env no coincide con la canonica "
                f"({ENV_DETECT})",
            )
        if ENV_ALLOW not in content:
            fail(
                errors,
                f"{rel}: la lista de plantillas permitidas no coincide con la canonica "
                f"({ENV_ALLOW})",
            )


def check_chain(errors: list[str]) -> None:
    """
    Verifica que el orden de las skills sea consistente y verificable.

    `skills/fleet-conventions/CHAIN.md` es la fuente de verdad del orden: una tabla de
    fases con las skills que entran en cada una. Cada `SKILL.md` declara las suyas en su
    seccion "En la cadena". Este chequeo exige que ambas coincidan.

    Sin esto, el orden vive solo en un diagrama de README que ningun agente lee en
    runtime: cada skill se carga sola y nadie sabe que existia una cadena.
    """
    chain_path = SKILLS_DIR / "fleet-conventions" / "CHAIN.md"
    if not chain_path.is_file():
        fail(errors, "falta skills/fleet-conventions/CHAIN.md (orden canonico de las skills)")
        return

    chain = chain_path.read_text(encoding="utf-8")

    # Tabla: | <fase> | <nombre> | `<skill>` | <cuando> |
    chain_phases: dict[str, set[int]] = {}
    phase_ids: set[int] = set()
    for line in chain.split("\n"):
        row = re.match(r"^\|\s*(\d+)\s*\|[^|]*\|\s*`([a-z0-9-]+)`\s*\|", line)
        if not row:
            continue
        phase = int(row.group(1))
        skill = row.group(2)
        phase_ids.add(phase)
        chain_phases.setdefault(skill, set()).add(phase)

    if not chain_phases:
        fail(errors, "CHAIN.md no tiene filas de fase con el formato | fase | nombre | `skill` | ... |")
        return

    expected_phases = set(range(min(phase_ids), max(phase_ids) + 1))
    if phase_ids != expected_phases:
        missing = sorted(expected_phases - phase_ids)
        fail(errors, f"CHAIN.md tiene fases con huecos: faltan {missing}")

    skills = sorted(
        p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")
    )
    for skill in skills:
        if skill not in chain_phases:
            fail(errors, f"CHAIN.md no menciona la skill '{skill}'")
    for skill in chain_phases:
        if skill not in skills:
            fail(errors, f"CHAIN.md declara '{skill}', que no existe en skills/")

    for skill in skills:
        path = SKILLS_DIR / skill / "SKILL.md"
        content = path.read_text(encoding="utf-8")
        match = re.search(r"^## En la cadena\s*$(.*?)(?=^## |\Z)", content, re.M | re.DOTALL)
        if not match:
            fail(errors, f"{skill}/SKILL.md: falta la seccion '## En la cadena'")
            continue
        declared = {int(n) for n in re.findall(r"^Fase (\d+)\b", match.group(1), re.M)}
        if not declared:
            fail(errors, f"{skill}/SKILL.md: la seccion 'En la cadena' no declara ninguna fase")
            continue
        unknown = declared - phase_ids
        if unknown:
            fail(errors, f"{skill}/SKILL.md: fases inexistentes en CHAIN.md: {sorted(unknown)}")
        expected = chain_phases.get(skill, set())
        if declared != expected:
            fail(
                errors,
                f"{skill}/SKILL.md: declara las fases {sorted(declared)} pero CHAIN.md "
                f"le asigna {sorted(expected)}",
            )


def main() -> int:
    errors: list[str] = []
    check_frontmatter(errors)
    check_reference_drift(errors)
    check_cjk(errors)
    check_fences(errors)
    check_env_pattern(errors)
    check_chain(errors)

    if errors:
        for message in errors:
            print(f"ERROR: {message}", file=sys.stderr)
        print(f"\n{len(errors)} problema(s) encontrado(s).", file=sys.stderr)
        return 1

    n_skills = len(list(SKILLS_DIR.glob("*/SKILL.md")))
    print(f"OK: {n_skills} skills, frontmatter valido, 0 glifos CJK, fences balanceados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
