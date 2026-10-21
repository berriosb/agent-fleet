"""Tests de `scripts/check-skills.py`.

El script es el validador del repo: si el validador se rompe, todo lo que el
repo afirma estar verificado deja de estar verificado. Estos tests fijan el
comportamiento de los chequeos que importan: frontmatter, fences, CJK y la
consistencia entre CHAIN.md y los SKILL.md.
"""

from __future__ import annotations

import unittest

from tests.helpers import DEFAULT_DESCRIPTION, ScriptTestCase, write_chain, write_skill


class TestFrontmatter(ScriptTestCase):
    script = "check-skills.py"

    def test_lee_los_campos_basicos(self):
        path = self.root / "SKILL.md"
        path.write_text(
            '---\nname: alpha\ndescription: "Una descripcion larga."\n'
            "license: MIT\nversion: 1.0.0\n---\n\nbody\n",
            encoding="utf-8",
        )
        fields, errors = self.module.parse_frontmatter(path)
        self.assertEqual(errors, [])
        self.assertEqual(fields["name"], "alpha")
        self.assertEqual(fields["license"], "MIT")
        self.assertEqual(fields["version"], "1.0.0")

    def test_sin_bloque_de_frontmatter(self):
        path = self.root / "SKILL.md"
        path.write_text("# Solo markdown\n", encoding="utf-8")
        fields, errors = self.module.parse_frontmatter(path)
        self.assertIsNone(fields)
        self.assertTrue(errors)

    def test_rechaza_tabuladores(self):
        path = self.root / "SKILL.md"
        path.write_text("---\nname: alpha\n\tbad: indent\n---\n", encoding="utf-8")
        _, errors = self.module.parse_frontmatter(path)
        self.assertTrue(any("tabulador" in e for e in errors))

    def test_rechaza_linea_yaml_invalida(self):
        path = self.root / "SKILL.md"
        path.write_text("---\nname alpha\n---\n", encoding="utf-8")
        _, errors = self.module.parse_frontmatter(path)
        self.assertTrue(any("YAML" in e for e in errors))

    def test_description_corta_se_reporta(self):
        self.use_root()
        write_skill(self.root, "alpha", description="corta")
        errors: list[str] = []
        self.module.check_frontmatter(errors)
        self.assertTrue(any("description demasiado corta" in e for e in errors))

    def test_name_debe_coincidir_con_el_directorio(self):
        self.use_root()
        skill_dir = self.root / "skills" / "alpha"
        skill_dir.mkdir(parents=True)
        frontmatter = (
            f'---\nname: beta\ndescription: "{DEFAULT_DESCRIPTION}"\n'
            "license: MIT\nversion: 1.0.0\n---\n"
        )
        (skill_dir / "SKILL.md").write_text(frontmatter, encoding="utf-8")
        errors: list[str] = []
        self.module.check_frontmatter(errors)
        self.assertTrue(any("no coincide con el directorio" in e for e in errors))


class TestFences(ScriptTestCase):
    script = "check-skills.py"

    def test_bloque_sin_cerrar(self):
        self.use_root()
        (self.root / "a.md").write_text("```python\ncode\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_fences(errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("nunca se cierra", errors[0])

    def test_fence_interno_del_mismo_largo_trunca(self):
        self.use_root()
        (self.root / "a.md").write_text(
            "```markdown\n```bash\necho hi\n```\n```\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_fences(errors)
        self.assertTrue(any("trunca" in e for e in errors))

    def test_fence_interno_mas_corto_es_contenido_legitimo(self):
        self.use_root()
        (self.root / "a.md").write_text(
            "````markdown\n```bash\necho hi\n```\n````\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_fences(errors)
        self.assertEqual(errors, [])


class TestCjk(ScriptTestCase):
    script = "check-skills.py"

    def test_detecta_glifos_cjk(self):
        self.use_root()
        # El glifo se escribe por escapes: un CJK literal en el fuente seria
        # el mismo error que este test detecta.
        (self.root / "a.md").write_text("\u6b63\u5e38\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_cjk(errors)
        self.assertTrue(any("glifos CJK" in e for e in errors))

    def test_texto_limpio_pasa(self):
        self.use_root()
        (self.root / "a.md").write_text("texto normal\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_cjk(errors)
        self.assertEqual(errors, [])

    def test_cobertura_rota_se_reporta(self):
        # Sin archivos de texto, el chequeo no cubrio nada: eso tambien es un fallo.
        self.use_root()
        (self.root / "a.bin").write_bytes(b"\x00\x01")
        errors: list[str] = []
        self.module.check_cjk(errors)
        self.assertTrue(any("cobertura" in e for e in errors))


class TestChain(ScriptTestCase):
    script = "check-skills.py"

    def test_fases_coincidentes_pasan(self):
        self.use_root()
        # Las fases de CHAIN.md tienen que ser contiguas: un hueco es un
        # problema del archivo, no una libertad de numeracion.
        write_skill(self.root, "alpha", phases=(1, 2))
        write_chain(self.root, {"alpha": {1, 2}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertEqual(errors, [])

    def test_skill_en_varias_fases_pasa(self):
        self.use_root()
        write_skill(self.root, "alpha", phases=(1, 3))
        write_chain(self.root, {"alpha": {1, 3}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertTrue(any("fases con huecos" in e for e in errors))

    def test_fase_distinta_se_reporta(self):
        self.use_root()
        write_skill(self.root, "alpha", phases=(1,))
        write_chain(self.root, {"alpha": {2}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertTrue(any("CHAIN.md le asigna" in e for e in errors))

    def test_skill_sin_mention_en_la_cadena(self):
        self.use_root()
        write_skill(self.root, "alpha", phases=(1,))
        write_chain(self.root, {"otra": {1}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertTrue(any("no menciona la skill" in e for e in errors))

    def test_skill_inexistente_en_la_cadena(self):
        self.use_root()
        write_skill(self.root, "alpha", phases=(1,))
        write_chain(self.root, {"alpha": {1}, "fantasma": {2}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertTrue(any("que no existe en skills/" in e for e in errors))

    def test_fases_con_huecos(self):
        self.use_root()
        write_skill(self.root, "alpha", phases=(1,))
        write_chain(self.root, {"alpha": {1}})
        chain = self.root / "skills" / "fleet-conventions" / "CHAIN.md"
        chain.write_text(
            chain.read_text(encoding="utf-8")
            + "| 3 | Nombre | `beta` | Cuando toque. |\n",
            encoding="utf-8",
        )
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertTrue(any("fases con huecos" in e for e in errors))


class TestForbiddenCli(ScriptTestCase):
    script = "check-skills.py"

    def test_typecheck_con_if_present_se_reporta(self):
        self.use_root()
        # El comando invalido se arma por partes: el archivo fuente no puede
        # contenerlo literal, porque el chequeo escanea tambien los tests.
        invalid = '"$tsc_bin" --noEmit --' + "if-present"
        (self.root / "run.sh").write_text(invalid + "\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_forbidden_cli(errors)
        self.assertTrue(any("flag invalido" in e for e in errors))

    def test_typecheck_correcto_pasa(self):
        self.use_root()
        (self.root / "run.sh").write_text('"$tsc_bin" --noEmit\n', encoding="utf-8")
        errors: list[str] = []
        self.module.check_forbidden_cli(errors)
        self.assertEqual(errors, [])


class TestCiUsesRunner(ScriptTestCase):
    script = "check-skills.py"

    def _workflow(self, body: str) -> None:
        workflows = self.root / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "qa.yml").write_text(body, encoding="utf-8")

    def test_ci_sin_invocar_el_runner_se_reporta(self):
        self.use_root()
        self._workflow("jobs:\n  static:\n    steps: []\n")
        errors: list[str] = []
        self.module.check_ci_uses_runner(errors)
        self.assertTrue(any("no invoca" in e for e in errors))

    def test_ci_con_comandos_propios_se_reporta(self):
        self.use_root()
        self._workflow(
            "jobs:\n  static:\n    steps:\n"
            "      - run: pnpm run lint --if-present || true\n"
            "      - run: bash run.sh --detect\n"
            "      - run: bash run.sh --scope static\n"
            "      - run: bash run.sh --scope tests\n"
        )
        errors: list[str] = []
        self.module.check_ci_uses_runner(errors)
        self.assertTrue(any("no debe aparecer en la CI" in e for e in errors))

    def test_ci_que_delega_pasa(self):
        self.use_root()
        self._workflow(
            "jobs:\n  static:\n    steps:\n"
            "      - run: bash run.sh --detect\n"
            "      - run: bash run.sh --scope static\n"
            "      - run: bash run.sh --scope tests\n"
        )
        errors: list[str] = []
        self.module.check_ci_uses_runner(errors)
        self.assertEqual(errors, [])


class TestAgentsMatchesChain(ScriptTestCase):
    script = "check-skills.py"

    def _write_agents(self, entries: dict[str, set[int]]) -> None:
        rows = []
        for skill, phases in sorted(entries.items()):
            for phase in sorted(phases):
                rows.append(f"| {phase} · Nombre | `{skill}` | Cuando toque. |")
        (self.root / "AGENTS.md").write_text(
            "# Contrato\n\n| Fase | Skill | Cuándo |\n|---|---|---|\n"
            + "\n".join(rows)
            + "\n",
            encoding="utf-8",
        )

    def test_fases_coincidentes_pasan(self):
        self.use_root()
        write_skill(self.root, "alpha", phases=(1, 2))
        write_chain(self.root, {"alpha": {1, 2}})
        self._write_agents({"alpha": {1, 2}})
        errors: list[str] = []
        self.module.check_agents_matches_chain(errors)
        self.assertEqual(errors, [])

    def test_fase_desactualizada_se_reporta(self):
        self.use_root()
        write_skill(self.root, "alpha", phases=(1, 2))
        write_chain(self.root, {"alpha": {1, 2}})
        self._write_agents({"alpha": {1}})
        errors: list[str] = []
        self.module.check_agents_matches_chain(errors)
        self.assertTrue(any("pero CHAIN.md le asigna" in e for e in errors))

    def test_skill_faltante_en_agents_se_reporta(self):
        self.use_root()
        write_skill(self.root, "alpha", phases=(1,))
        write_chain(self.root, {"alpha": {1}})
        self._write_agents({})
        errors: list[str] = []
        self.module.check_agents_matches_chain(errors)
        self.assertTrue(any("no tiene una tabla de fases" in e for e in errors))


class TestReadmeListsSkills(ScriptTestCase):
    script = "check-skills.py"

    def test_skill_faltante_se_reporta(self):
        self.use_root()
        write_skill(self.root, "alpha")
        (self.root / "README.md").write_text(
            "| `skills/otra/` | Otra cosa |\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_readme_lists_skills(errors)
        self.assertTrue(any("no lista la skill 'alpha'" in e for e in errors))

    def test_todas_las_skills_listadas_pasan(self):
        self.use_root()
        write_skill(self.root, "alpha")
        write_skill(self.root, "beta")
        (self.root / "README.md").write_text(
            "| `skills/alpha/` | A |\n| `skills/beta/` | B |\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_readme_lists_skills(errors)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
