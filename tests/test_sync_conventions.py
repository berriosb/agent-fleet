"""Tests de `scripts/sync-conventions.py`.

La garantia que importa del sync es que sea determinista: el archivo generado
tiene que ser byte a byte el mismo hoy y dentro de un mes, sin fecha ni rutas
locales. Si el render deja de ser determinista, `--check` en CI empieza a
fallar sin que nadie haya tocado el vault.
"""

from __future__ import annotations

import unittest

from tests.helpers import ScriptTestCase


class TestExtractSections(ScriptTestCase):
    script = "sync-conventions.py"

    def test_parte_por_encabezados_h2(self):
        markdown = "# H1\n\n## Uno\n\ncuerpo uno\n\n## Dos\n\ncuerpo dos\n"
        sections = self.module.extract_sections(markdown)
        self.assertEqual([title for title, _ in sections], ["Uno", "Dos"])

    def test_ignora_h2_dentro_de_un_fence(self):
        markdown = "## Uno\n\n```\n## no soy un encabezado\n```\n\nfin\n"
        sections = self.module.extract_sections(markdown)
        self.assertEqual([title for title, _ in sections], ["Uno"])
        self.assertTrue(any("## no soy un encabezado" in line for line in sections[0][1]))

    def test_devuelve_vacio_sin_h2(self):
        self.assertEqual(self.module.extract_sections("# Solo h1\n"), [])


class TestRender(ScriptTestCase):
    script = "sync-conventions.py"

    def _curated(self) -> None:
        curated = self.root / "SKILL.md"
        curated.write_text(
            '---\nname: fleet-conventions\ndescription: "Una descripcion larga."\n'
            "license: MIT\nversion: 1.0.0\n---\n",
            encoding="utf-8",
        )
        self.module.CURATED = curated

    def test_es_determinista(self):
        self._curated()
        sections = [("Uno", ["linea uno"]), ("Dos", ["linea dos"])]
        first = self.module.render(sections, "sha-de-prueba")
        second = self.module.render(sections, "sha-de-prueba")
        self.assertEqual(first, second)

    def test_no_trae_rutas_locales(self):
        self._curated()
        text = self.module.render([("Uno", ["contenido"])], "sha-de-prueba")
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("/home/", text)

    def test_no_trae_fecha(self):
        self._curated()
        text = self.module.render([("Uno", ["contenido"])], "sha-de-prueba")
        # El render no lleva la fecha del dia: es lo que lo hace reproducible.
        self.assertNotIn("generado:", text.lower())

    def test_el_frontmatter_se_copia_del_curado(self):
        self._curated()
        text = self.module.render([("Uno", ["contenido"])], "sha-de-prueba")
        self.assertIn("name: fleet-conventions", text)
        self.assertIn("Una descripcion larga.", text)

    def test_aborta_si_hay_glifos_cjk(self):
        self._curated()
        with self.assertRaises(SystemExit):
            self.module.render([("Uno", ["\u4e00"])], "sha-de-prueba")


class TestSha256(ScriptTestCase):
    script = "sync-conventions.py"

    def test_es_estable(self):
        self.assertEqual(
            self.module.sha256("texto"), self.module.sha256("texto")
        )

    def test_cambia_con_el_contenido(self):
        self.assertNotEqual(
            self.module.sha256("uno"), self.module.sha256("otro")
        )


if __name__ == "__main__":
    unittest.main()
