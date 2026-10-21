"""Helpers compartidos por los tests.

Los scripts de `scripts/` tienen guion en el nombre, asi que no se importan con
`import`. Este modulo los carga por ruta, y arma los fixtures minimos que
necesitan: un repo de skills con su CHAIN.md.

Todo es stdlib: los tests no agregan dependencias al repo.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

DEFAULT_DESCRIPTION = (
    "Una descripcion lo bastante larga para que el agente sepa si la skill aplica."
)

SKILL_TEMPLATE = """---
name: {name}
description: "{description}"
license: {license}
version: {version}
---

# {name}

## En la cadena

{phase_lines}

{body}
"""

CHAIN_TEMPLATE = """# La cadena de skills

| Fase | Nombre | Skill | Se carga cuando |
|---|---|---|---|
{rows}
"""


def load_script(filename: str):
    """Carga un script de `scripts/` por nombre, con guion incluido."""
    path = SCRIPTS_DIR / filename
    module_name = path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_skill(
    root: Path,
    name: str,
    phases: tuple[int, ...] = (1,),
    description: str = DEFAULT_DESCRIPTION,
    license_: str = "MIT",
    version: str = "1.0.0",
    body: str = "",
) -> Path:
    """Crea `skills/<name>/SKILL.md` con su seccion 'En la cadena'."""
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    phase_lines = "\n".join(f"Fase {phase} — Diseno. Cuando toque." for phase in phases)
    path = skill_dir / "SKILL.md"
    path.write_text(
        SKILL_TEMPLATE.format(
            name=name,
            description=description,
            license=license_,
            version=version,
            phase_lines=phase_lines,
            body=body,
        ),
        encoding="utf-8",
    )
    return path


def write_chain(root: Path, entries: dict[str, set[int]]) -> Path:
    """Crea `skills/fleet-conventions/CHAIN.md` con la tabla de fases."""
    rows = []
    for skill, phases in sorted(entries.items()):
        for phase in sorted(phases):
            rows.append(f"| {phase} | Nombre | `{skill}` | Cuando toque. |")
    chain_dir = root / "skills" / "fleet-conventions"
    chain_dir.mkdir(parents=True, exist_ok=True)
    path = chain_dir / "CHAIN.md"
    path.write_text(CHAIN_TEMPLATE.format(rows="\n".join(rows)), encoding="utf-8")
    return path


class ScriptTestCase(unittest.TestCase):
    """Base con un directorio temporal y los scripts ya cargados."""

    script: str = ""
    # El modulo cargado se asigna en setUpClass. Se declara aca para que los
    # type checkers lo vean como atributo de clase y no como un invento.
    module: Any

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_script(cls.script)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def use_root(self, module=None) -> None:
        """Apunta los paths del script al directorio temporal."""
        module = module or self.module
        module.REPO = self.root
        module.SKILLS_DIR = self.root / "skills"
