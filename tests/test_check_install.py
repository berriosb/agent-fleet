"""Tests de `scripts/check-install.py`.

Este script verifica el estado de la maquina: que las skills esten enlazadas
donde los agentes las buscan y que no queden copias divergentes. Su logica de
expansion de globs y de resolucion de enlaces es lo unico que se puede testear
sin tocar la maquina.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.helpers import ScriptTestCase


class TestExpand(ScriptTestCase):
    script = "check-install.py"

    def test_ignora_lo_inexistente(self) -> None:
        found = self.module.expand(str(self.root / "nope" / "*"))
        self.assertEqual(found, [])

    def test_devuelve_solo_directorios(self) -> None:
        (self.root / "a" / "b").mkdir(parents=True)
        (self.root / "a" / "c.txt").write_text("x", encoding="utf-8")
        found = self.module.expand(str(self.root / "a" / "*"))
        self.assertEqual([path.name for path in found], ["b"])

    def test_expande_dos_niveles(self) -> None:
        (self.root / "a" / "b").mkdir(parents=True)
        (self.root / "c" / "d").mkdir(parents=True)
        found = self.module.expand(str(self.root / "*" / "*"))
        self.assertEqual(sorted(path.name for path in found), ["b", "d"])


class TestResolvesIntoRepo(ScriptTestCase):
    script = "check-install.py"

    def _skills(self) -> Path:
        skills = self.root / "skills"
        (skills / "alpha").mkdir(parents=True)
        return skills

    def test_enlace_al_repo_es_valido(self) -> None:
        skills = self._skills()
        link = self.root / "link"
        link.symlink_to(skills / "alpha")
        self.module.SKILLS_DIR = skills
        self.assertTrue(self.module.resolves_into_repo(link))

    def test_directorio_real_dentro_del_repo_es_valido(self) -> None:
        # La funcion responde "esto resuelve dentro de skills/ del repo", no
        # "esto es un enlace". El symlink lo revisa el caller antes.
        skills = self._skills()
        self.module.SKILLS_DIR = skills
        self.assertTrue(self.module.resolves_into_repo(skills / "alpha"))

    def test_enlace_a_otro_lugar_no_es_valido(self) -> None:
        skills = self._skills()
        other = self.root / "otro"
        other.mkdir()
        link = self.root / "link"
        link.symlink_to(other)
        self.module.SKILLS_DIR = skills
        self.assertFalse(self.module.resolves_into_repo(link))


if __name__ == "__main__":
    unittest.main()
