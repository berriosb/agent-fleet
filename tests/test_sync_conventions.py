"""Tests de `scripts/sync-conventions.py`.

La garantia que importa del sync es que sea determinista: el archivo generado
tiene que ser byte a byte el mismo hoy y dentro de un mes, sin fecha ni rutas
locales. Si el render deja de ser determinista, `--check` en CI empieza a
fallar sin que nadie haya tocado el vault.
"""

from __future__ import annotations

import sys
import unittest

from tests.helpers import ScriptTestCase


class TestExtractSections(ScriptTestCase):
    script = "sync-conventions.py"

    def test_parte_por_encabezados_h2(self) -> None:
        markdown = "# H1\n\n## Uno\n\ncuerpo uno\n\n## Dos\n\ncuerpo dos\n"
        sections = self.module.extract_sections(markdown)
        self.assertEqual([title for title, _ in sections], ["Uno", "Dos"])

    def test_ignora_h2_dentro_de_un_fence(self) -> None:
        markdown = "## Uno\n\n```\n## no soy un encabezado\n```\n\nfin\n"
        sections = self.module.extract_sections(markdown)
        self.assertEqual([title for title, _ in sections], ["Uno"])
        self.assertTrue(any("## no soy un encabezado" in line for line in sections[0][1]))

    def test_devuelve_vacio_sin_h2(self) -> None:
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

    def test_es_determinista(self) -> None:
        self._curated()
        sections = [("Uno", ["linea uno"]), ("Dos", ["linea dos"])]
        first = self.module.render(sections, "sha-de-prueba")
        second = self.module.render(sections, "sha-de-prueba")
        self.assertEqual(first, second)

    def test_no_trae_rutas_locales(self) -> None:
        self._curated()
        text = self.module.render([("Uno", ["contenido"])], "sha-de-prueba")
        self.assertNotIn(str(self.root), text)
        self.assertNotIn("/home/", text)

    def test_no_trae_fecha(self) -> None:
        self._curated()
        text = self.module.render([("Uno", ["contenido"])], "sha-de-prueba")
        # El render no lleva la fecha del dia: es lo que lo hace reproducible.
        self.assertNotIn("generado:", text.lower())

    def test_el_frontmatter_se_copia_del_curado(self) -> None:
        self._curated()
        text = self.module.render([("Uno", ["contenido"])], "sha-de-prueba")
        self.assertIn("name: fleet-conventions", text)
        self.assertIn("Una descripcion larga.", text)

    def test_aborta_si_hay_glifos_cjk(self) -> None:
        self._curated()
        with self.assertRaises(SystemExit):
            self.module.render([("Uno", ["\u4e00"])], "sha-de-prueba")


class TestSha256(ScriptTestCase):
    script = "sync-conventions.py"

    def test_es_estable(self) -> None:
        self.assertEqual(
            self.module.sha256("texto"), self.module.sha256("texto")
        )

    def test_cambia_con_el_contenido(self) -> None:
        self.assertNotEqual(
            self.module.sha256("uno"), self.module.sha256("otro")
        )


class TestSanitizeLocalPaths(ScriptTestCase):
    script = "sync-conventions.py"

    def test_reemplaza_la_ruta_local_del_vault(self) -> None:
        local = str(self.module.VAULT_ROOTS[0])
        limpio = self.module.sanitize_local_paths(f"- **Ruta:** `{local}/`\n")
        self.assertNotIn(local, limpio)
        self.assertIn("Agent-Shared/", limpio)

    def test_no_toca_lo_que_no_es_una_ruta(self) -> None:
        texto = "nada que ver aca\n"
        self.assertEqual(self.module.sanitize_local_paths(texto), texto)

    def test_el_render_no_trae_rutas_locales(self) -> None:
        curated = self.root / "SKILL.md"
        curated.write_text(
            '---\nname: fleet-conventions\ndescription: "Una descripcion larga."\n'
            "license: MIT\nversion: 1.0.0\n---\n",
            encoding="utf-8",
        )
        self.module.CURATED = curated
        local = str(self.module.VAULT_ROOTS[0])
        text = self.module.render([("Uno", [f"- **Ruta:** `{local}/`"])], "sha-de-prueba")
        self.assertNotIn(local, text)
        self.assertNotIn("/home/", text)


class TestRequireVault(ScriptTestCase):
    script = "sync-conventions.py"

    def _sin_vault(self) -> None:
        """Deja el vault inaccesible y el archivo destino presente."""
        self.use_root()
        target = self.root / "references" / "vault-conventions.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("contenido\n", encoding="utf-8")
        self.module.TARGET = target
        self.module.read_sources = lambda: [("http://vault/x", None, "404")]

    def _main(self, *args: str) -> int:
        argv = sys.argv
        try:
            sys.argv = ["sync-conventions.py", *args]
            return int(self.module.main())
        finally:
            sys.argv = argv

    def test_require_vault_falla_si_no_se_puede_comparar(self) -> None:
        # Un chequeo que no comparo no puede pasar por verde. Sin este flag, el
        # job de CI pasaba en verde sin verificar la referencia.
        self._sin_vault()
        with self.assertRaises(SystemExit):
            self._main("--check", "--require-vault")

    def test_sin_require_vault_el_skip_sigue_siendo_permitido(self) -> None:
        # El camino local y el de release.sh no tienen token: no pueden
        # empezar a fallar por eso.
        self._sin_vault()
        self.assertEqual(self._main("--check"), 0)


if __name__ == "__main__":
    unittest.main()
