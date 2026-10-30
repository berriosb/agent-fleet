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
8. comandos replicados: cada comando que vive en mas de un sitio esta en su forma
   canonica en todos ellos (mismo mecanismo que el punto 6, para los comandos).
9. reglas replicadas: cada regla de comportamiento que vive en mas de un SKILL.md esta
   en su forma canonica en todos ellos (mismo mecanismo que el punto 8, para las reglas).
10. flags prohibidos: ningun ejecutable le pasa a una herramienta un flag que no
    acepta. `--if-present` a `tsc` es el caso que motivo el chequeo.
11. la CI no reimplementa el gate: invoca al runner y no trae comandos propios de
    lint, tipos o tests. Una copia propia diverge, y divergir en silencio es
    exactamente como se rompe un gate.
12. AGENTS.md declara las mismas fases que CHAIN.md, y el README lista todas las
    skills. AGENTS.md es lo que un agente lee de verdad: su tabla no puede
    quedar vieja en silencio.

Uso
───
    python3 scripts/check-skills.py            # exit 1 si algo falla
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

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

class ReplicatedCommand(TypedDict):
    """La forma de una entrada de REPLICATED_COMMANDS."""

    name: str
    canonical: str
    sites: list[Path]


class SharedRule(TypedDict):
    """La forma de una entrada de SHARED_RULES."""

    name: str
    canonical: str
    sites: list[Path]


# Reglas que viven en mas de un SKILL.md. La forma canonica tiene que aparecer
# en todos los sitios: una regla replicada se vence en uno de ellos sin que
# nada lo note, y el resultado es que un agente ve dos versiones de lo mismo.
#
# El que motivo esto: la regla del "el test cambia en el mismo commit que la
# implementacion" para detectar al agente que toca los tests para que pasen.
# Vive en la skill que decide los commits y en la skill que escribe el codigo;
# si una de las dos la pierde, la trampa queda sin detectar.
SHARED_RULES: list[SharedRule] = [
    {
        "name": "el test cambia en el mismo commit que la implementacion",
        "canonical": "changes in the same commit as the implementation",
        "sites": [
            SKILLS_DIR / "work-unit-commits" / "SKILL.md",
            SKILLS_DIR / "fleet-pair" / "SKILL.md",
        ],
    },
]


# Comandos que el repo replica en mas de un sitio. Cada entrada declara la forma
# canonica y los sitios donde debe aparecer. Si alguien edita uno solo, este
# chequeo lo reporta: es el mismo mecanismo que ya funciona para la regex de
# `.env`, aplicado a los comandos.
REPLICATED_COMMANDS: list[ReplicatedCommand] = [
    {
        "name": "typecheck de TypeScript",
        "canonical": "--noEmit",
        "sites": [
            SKILLS_DIR / "pre-push-qa" / "scripts" / "run.sh",
            SKILLS_DIR / "pre-push-qa" / "SKILL.md",
        ],
    },
]

# Flags que la herramienta destino NO acepta. Un flag invalido no rompe nada
# de forma visible: la herramienta lo rechaza, el script sigue, y el gate deja
# de cubrir el caso que cubria.
#
# El que motivo esto: `tsc --noEmit --if-present`. `--if-present` pertenece al
# runner de scripts (pnpm/npm run), no al compilador. tsc responde "Unknown
# compiler option '--if-present'" y sale con codigo 1, asi que el gate rechazaba
# TODOS los repos TypeScript. Vivia en tres sitios y nadie lo verificaba.
FORBIDDEN_CLI = [
    (
        r"[^\n]*--noEmit[^\n]*--if-present",
        (
            "el typecheck no puede recibir `--if-present`: ese flag pertenece al runner "
            "de scripts (pnpm/npm run), no a tsc. tsc responde 'Unknown compiler option' "
            "y sale con codigo 1, asi que el gate rechazaba TODOS los repos TypeScript."
        ),
    ),
    (
        r"\btsc\b[^\n]*--if-present",
        (
            "`--if-present` es un flag del runner de scripts (pnpm/npm run), no de tsc. "
            "tsc responde 'Unknown compiler option' y sale con codigo 1: el gate "
            "rechazaba todos los repos TypeScript."
        ),
    ),
]

# Comandos que la CI no debe traer: los ejecuta el runner. Una copia propia
# diverge, y esa copia fue la que dejo de fallar.
FORBIDDEN_IN_WORKFLOW = [
    "tsc --noEmit",
    "ruff check",
    "mypy .",
    "pytest -q",
    "pnpm test",
    "npm test",
    "yarn test",
    "bun test",
    "run lint",
    "run build",
    "terraform fmt",
]

# La CI tiene que invocar el runner, no reimplementarlo.
REQUIRED_IN_WORKFLOW = [
    "run.sh --detect",
    "run.sh --scope static",
    "run.sh --scope tests",
]

# Archivos donde un flag invalido rompe el gate. Los `.md` quedan afuera a
# proposito: la documentacion puede (y debe) nombrar el flag que se prohibe.
CODE_SUFFIXES = {".sh", ".js", ".yml", ".yaml", ".py"}

# Formato de las tablas de fases. Son dos archivos con el mismo contenido y dos
# formatos distintos, asi que cada uno tiene su patron.
#   CHAIN.md:  | 3 | Verificacion | `pre-push-qa` | ... |
#   AGENTS.md: | 3 · Verificacion | `pre-push-qa` | ... |
CHAIN_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|[^|]*\|\s*`([a-z0-9-]+)`\s*\|")
AGENTS_ROW_RE = re.compile(r"^\|\s*(\d+)\s*·\s*[^|]*\|\s*`([a-z0-9-]+)`\s*\|")


def parse_phase_table(text: str, row_re: re.Pattern[str]) -> dict[str, set[int]]:
    """Extrae skill -> fases de una tabla de fases."""
    phases: dict[str, set[int]] = {}
    for line in text.split("\n"):
        row = row_re.match(line)
        if not row:
            continue
        phases.setdefault(row.group(2), set()).add(int(row.group(1)))
    return phases

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


def repo_files() -> list[str]:
    """Archivos que importan: los commiteados mas los nuevos sin trackear.

    `git ls-files --cached --others --exclude-standard` da exactamente eso: lo
    que esta en el indice, mas lo que se sumaria al proximo commit, sin los
    archivos ignorados. Es el conjunto que tiene que estar limpio, porque un
    `.md` recien escrito todavia no esta commiteado y su regla es que se
    chequee antes de entregarlo.

    Los dos chequeos de texto (CJK y fences) usan esta misma lista. Antes uno
    miraba los trackeados y el otro todo el directorio, y por eso un archivo
    sin trackear rompia fences pero no CJK.
    """
    try:
        listed = subprocess.run(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split("\0")
    except (subprocess.CalledProcessError, FileNotFoundError):
        listed = [str(p.relative_to(REPO)) for p in REPO.rglob("*") if p.is_file()]
    return [rel for rel in filter(None, listed)]


def check_cjk(errors: list[str]) -> None:
    tracked = repo_files()

    checked = 0
    for rel in tracked:
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
    for rel in repo_files():
        if not rel.endswith(".md"):
            continue
        path = REPO / rel
        if not path.is_file():
            continue
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


def check_replicated_commands(errors: list[str]) -> None:
    """Un comando replicado tiene que estar en su forma canonica en todos los sitios."""
    for spec in REPLICATED_COMMANDS:
        for path in spec["sites"]:
            if not path.is_file():
                fail(errors, f"falta {path.relative_to(REPO)}")
                continue
            content = path.read_text(encoding="utf-8")
            if spec["canonical"] not in content:
                fail(
                    errors,
                    f"{path.relative_to(REPO)}: no usa la forma canonica de "
                    f"{spec['name']} ('{spec['canonical']}')",
                )


def check_shared_rules(errors: list[str]) -> None:
    """Una regla replicada tiene que estar en todos los sitios donde vive.

    Es el mismo mecanismo que el de los comandos replicados, aplicado a las
    reglas del comportamiento: si la forma canonica aparece en un sitio y no
    en el otro, la regla ya no es una sola regla, y el agente recibe dos
    versiones distintas de lo mismo.
    """
    for spec in SHARED_RULES:
        for path in spec["sites"]:
            if not path.is_file():
                fail(errors, f"falta {path.relative_to(REPO)}")
                continue
            content = path.read_text(encoding="utf-8")
            if spec["canonical"] not in content:
                fail(
                    errors,
                    f"{path.relative_to(REPO)}: no dice '{spec['canonical']}' "
                    f"({spec['name']})",
                )


def iter_code_files() -> list[Path]:
    """Archivos ejecutables del repo: shell, js, python y workflows.

    Este archivo queda afuera: define los patrones prohibidos y los documenta,
    asi que los contiene literalmente. Un archivo no puede declararse invalido
    a si mismo.
    """
    self_path = Path(__file__).resolve()
    found: list[Path] = []
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts or "node_modules" in path.parts:
            continue
        if path.resolve() == self_path:
            continue
        if path.suffix.lower() in CODE_SUFFIXES:
            found.append(path)
    return sorted(found)


def check_forbidden_cli(errors: list[str]) -> None:
    """Ningun ejecutable puede pasarle a una herramienta un flag que no acepta."""
    for path in iter_code_files():
        content = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, why in FORBIDDEN_CLI:
            for match in re.finditer(pattern, content):
                lineno = content[: match.start()].count("\n") + 1
                fail(errors, f"{path.relative_to(REPO)}:{lineno}: flag invalido — {why}")


def check_ci_uses_runner(errors: list[str]) -> None:
    """La CI invoca el runner; no trae su propia copia de los comandos.

    La duplicacion es la causa de fondo de los dos bugs mas caros del gate: la
    copia de la CI dejo de fallar porque cada chequeo terminaba en `|| true` y
    los tests iban por un pipe que devuelve el codigo de `tail`. Si la CI
    vuelve a traer comandos propios, ese arreglo se deshace en silencio.
    """
    workflows = sorted((REPO / ".github" / "workflows").glob("*.yml"))
    if not workflows:
        fail(errors, "no hay workflows en .github/workflows/")
        return

    for path in workflows:
        content = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO)
        for command in FORBIDDEN_IN_WORKFLOW:
            if command in content:
                fail(
                    errors,
                    f"{rel}: '{command}' no debe aparecer en la CI. Los comandos del "
                    "gate se ejecutan desde skills/pre-push-qa/scripts/run.sh.",
                )

    reusable = REPO / ".github" / "workflows" / "qa.yml"
    if reusable.is_file():
        content = reusable.read_text(encoding="utf-8")
        for required in REQUIRED_IN_WORKFLOW:
            if required not in content:
                fail(
                    errors,
                    f"{reusable.relative_to(REPO)}: no invoca '{required}'. La CI tiene "
                    "que delegar en el runner para que local y remoto apliquen los "
                    "mismos criterios.",
                )


def check_agents_matches_chain(errors: list[str]) -> None:
    """AGENTS.md tiene que declarar las mismas fases que CHAIN.md.

    AGENTS.md es el archivo que un agente lee de verdad: es lo que se carga sin
    depender de que el agente "se acuerde" de buscarla. Si su tabla queda
    vieja, el orden que el agente sigue es otro, y no hay ninguna señal: el
    error aparece semanas despues, en el comportamiento de otro agente.
    """
    chain_path = SKILLS_DIR / "fleet-conventions" / "CHAIN.md"
    agents_path = REPO / "AGENTS.md"
    if not chain_path.is_file() or not agents_path.is_file():
        fail(errors, "faltan AGENTS.md o CHAIN.md para comparar la cadena")
        return

    chain_phases = parse_phase_table(chain_path.read_text(encoding="utf-8"), CHAIN_ROW_RE)
    agents_phases = parse_phase_table(agents_path.read_text(encoding="utf-8"), AGENTS_ROW_RE)

    if not agents_phases:
        fail(
            errors,
            "AGENTS.md no tiene una tabla de fases con el formato "
            "| fase · nombre | `skill` | ... |",
        )
        return

    for skill, phases in sorted(chain_phases.items()):
        if skill not in agents_phases:
            fail(errors, f"AGENTS.md no menciona la skill '{skill}'")
        elif agents_phases[skill] != phases:
            fail(
                errors,
                f"AGENTS.md: '{skill}' declara las fases {sorted(agents_phases[skill])} "
                f"pero CHAIN.md le asigna {sorted(phases)}",
            )
    for skill in sorted(agents_phases):
        if skill not in chain_phases:
            fail(errors, f"AGENTS.md declara '{skill}', que no esta en CHAIN.md")


def check_readme_lists_skills(errors: list[str]) -> None:
    """Cada skill tiene que aparecer en la tabla de rutas del README."""
    readme = REPO / "README.md"
    if not readme.is_file():
        fail(errors, "falta README.md")
        return
    content = readme.read_text(encoding="utf-8")
    for skill in sorted(p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")):
        if f"skills/{skill}/" not in content:
            fail(errors, f"README.md no lista la skill '{skill}' (falta skills/{skill}/)")


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
    chain_phases = parse_phase_table(chain, CHAIN_ROW_RE)
    phase_ids: set[int] = set()
    for phases in chain_phases.values():
        phase_ids |= phases

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
        match = re.search(
            r"^## En la cadena\s*$(.*?)(?=^## |\Z)", content, re.MULTILINE | re.DOTALL
        )
        if not match:
            fail(errors, f"{skill}/SKILL.md: falta la seccion '## En la cadena'")
            continue
        declared = {
            int(n) for n in re.findall(r"^Fase (\d+)\b", match.group(1), re.MULTILINE)
        }
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
    check_replicated_commands(errors)
    check_shared_rules(errors)
    check_forbidden_cli(errors)
    check_ci_uses_runner(errors)
    check_chain(errors)
    check_agents_matches_chain(errors)
    check_readme_lists_skills(errors)

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
