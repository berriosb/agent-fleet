"""Tests de `scripts/check-skills.py`.

El script es el validador del repo: si el validador se rompe, todo lo que el
repo afirma estar verificado deja de estar verificado. Estos tests fijan el
comportamiento de los chequeos que importan: frontmatter, fences, CJK y la
consistencia entre CHAIN.md y los SKILL.md.
"""

from __future__ import annotations

import unittest

from tests.helpers import DEFAULT_DESCRIPTION, ScriptTestCase, write_chain, write_skill

# La forma canonica de la regla replicada. Vive aca y en
# scripts/check-skills.py (SHARED_RULES): si cambia en uno y no en el otro, el
# test falla en vez de dejar que el repo se quede mudo.
#
# Sin mayuscula al inicio a proposito: la frase tiene que aparecer en medio de
# una oracion en los dos sitios, y no al principio de otra.
CANONICAL_RULE = "changes in the same commit as the implementation"


class TestFrontmatter(ScriptTestCase):
    script = "check-skills.py"

    def test_lee_los_campos_basicos(self) -> None:
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

    def test_sin_bloque_de_frontmatter(self) -> None:
        path = self.root / "SKILL.md"
        path.write_text("# Solo markdown\n", encoding="utf-8")
        fields, errors = self.module.parse_frontmatter(path)
        self.assertIsNone(fields)
        self.assertTrue(errors)

    def test_rechaza_tabuladores(self) -> None:
        path = self.root / "SKILL.md"
        path.write_text("---\nname: alpha\n\tbad: indent\n---\n", encoding="utf-8")
        _, errors = self.module.parse_frontmatter(path)
        self.assertTrue(any("tabulador" in e for e in errors))

    def test_rechaza_linea_yaml_invalida(self) -> None:
        path = self.root / "SKILL.md"
        path.write_text("---\nname alpha\n---\n", encoding="utf-8")
        _, errors = self.module.parse_frontmatter(path)
        self.assertTrue(any("YAML" in e for e in errors))

    def test_description_corta_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", description="corta")
        errors: list[str] = []
        self.module.check_frontmatter(errors)
        self.assertTrue(any("description demasiado corta" in e for e in errors))

    def test_name_debe_coincidir_con_el_directorio(self) -> None:
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

    def test_bloque_sin_cerrar(self) -> None:
        self.use_root()
        (self.root / "a.md").write_text("```python\ncode\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_fences(errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("nunca se cierra", errors[0])

    def test_fence_interno_del_mismo_largo_trunca(self) -> None:
        self.use_root()
        (self.root / "a.md").write_text(
            "```markdown\n```bash\necho hi\n```\n```\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_fences(errors)
        self.assertTrue(any("trunca" in e for e in errors))

    def test_fence_interno_mas_corto_es_contenido_legitimo(self) -> None:
        self.use_root()
        (self.root / "a.md").write_text(
            "````markdown\n```bash\necho hi\n```\n````\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_fences(errors)
        self.assertEqual(errors, [])


class TestCjk(ScriptTestCase):
    script = "check-skills.py"

    def test_detecta_glifos_cjk(self) -> None:
        self.use_root()
        # El glifo se escribe por escapes: un CJK literal en el fuente seria
        # el mismo error que este test detecta.
        (self.root / "a.md").write_text("\u6b63\u5e38\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_cjk(errors)
        self.assertTrue(any("glifos CJK" in e for e in errors))

    def test_texto_limpio_pasa(self) -> None:
        self.use_root()
        (self.root / "a.md").write_text("texto normal\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_cjk(errors)
        self.assertEqual(errors, [])

    def test_cobertura_rota_se_reporta(self) -> None:
        # Sin archivos de texto, el chequeo no cubrio nada: eso tambien es un fallo.
        self.use_root()
        (self.root / "a.bin").write_bytes(b"\x00\x01")
        errors: list[str] = []
        self.module.check_cjk(errors)
        self.assertTrue(any("cobertura" in e for e in errors))


class TestChain(ScriptTestCase):
    script = "check-skills.py"

    def test_fases_coincidentes_pasan(self) -> None:
        self.use_root()
        # Las fases de CHAIN.md tienen que ser contiguas: un hueco es un
        # problema del archivo, no una libertad de numeracion.
        write_skill(self.root, "alpha", phases=(1, 2))
        write_chain(self.root, {"alpha": {1, 2}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertEqual(errors, [])

    def test_skill_en_varias_fases_pasa(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", phases=(1, 3))
        write_chain(self.root, {"alpha": {1, 3}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertTrue(any("fases con huecos" in e for e in errors))

    def test_fase_distinta_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", phases=(1,))
        write_chain(self.root, {"alpha": {2}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertTrue(any("CHAIN.md le asigna" in e for e in errors))

    def test_skill_sin_mention_en_la_cadena(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", phases=(1,))
        write_chain(self.root, {"otra": {1}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertTrue(any("no menciona la skill" in e for e in errors))

    def test_skill_inexistente_en_la_cadena(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", phases=(1,))
        write_chain(self.root, {"alpha": {1}, "fantasma": {2}})
        errors: list[str] = []
        self.module.check_chain(errors)
        self.assertTrue(any("que no existe en skills/" in e for e in errors))

    def test_fases_con_huecos(self) -> None:
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

    def test_typecheck_con_if_present_se_reporta(self) -> None:
        self.use_root()
        # El comando invalido se arma por partes: el archivo fuente no puede
        # contenerlo literal, porque el chequeo escanea tambien los tests.
        invalid = '"$tsc_bin" --noEmit --' + "if-present"
        (self.root / "run.sh").write_text(invalid + "\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_forbidden_cli(errors)
        self.assertTrue(any("flag invalido" in e for e in errors))

    def test_typecheck_correcto_pasa(self) -> None:
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

    def test_ci_sin_invocar_el_runner_se_reporta(self) -> None:
        self.use_root()
        self._workflow("jobs:\n  static:\n    steps: []\n")
        errors: list[str] = []
        self.module.check_ci_uses_runner(errors)
        self.assertTrue(any("no invoca" in e for e in errors))

    def test_ci_con_comandos_propios_se_reporta(self) -> None:
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

    def test_ci_que_delega_pasa(self) -> None:
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

    def test_ci_con_supresor_de_exit_code_se_reporta(self) -> None:
        # La regresion que el repo ya arreglo una vez: el gate corre pero su
        # codigo de salida se descarta, y la CI vuelve a ser decorativa.
        self.use_root()
        self._workflow(
            "jobs:\n  static:\n    steps:\n"
            "      - run: bash run.sh --detect\n"
            "      - run: bash run.sh --scope static || true\n"
            "      - run: bash run.sh --scope tests\n"
        )
        errors: list[str] = []
        self.module.check_ci_uses_runner(errors)
        self.assertTrue(any("|| true" in e for e in errors))

    def test_ci_con_pipe_que_traga_el_exit_code_se_reporta(self) -> None:
        # `... | tail` devuelve el codigo de `tail`, no el del gate.
        self.use_root()
        self._workflow(
            "jobs:\n  static:\n    steps:\n"
            "      - run: bash run.sh --detect\n"
            "      - run: bash run.sh --scope static | tail -20\n"
            "      - run: bash run.sh --scope tests\n"
        )
        errors: list[str] = []
        self.module.check_ci_uses_runner(errors)
        self.assertTrue(any("| tail" in e for e in errors))

    def test_ci_con_continue_on_error_se_reporta(self) -> None:
        self.use_root()
        self._workflow(
            "jobs:\n  static:\n    steps:\n"
            "      - run: bash run.sh --detect\n"
            "      - name: Run static gate\n"
            "        continue-on-error: true\n"
            "        run: bash run.sh --scope static\n"
            "      - run: bash run.sh --scope tests\n"
        )
        errors: list[str] = []
        self.module.check_ci_uses_runner(errors)
        self.assertTrue(any("continue-on-error" in e for e in errors))

    def test_ci_con_invocacion_que_no_ejecuta_el_gate_se_reporta(self) -> None:
        # El string esta, el gate no corre. Un chequeo de presencia no lo ve.
        self.use_root()
        self._workflow(
            "jobs:\n  static:\n    steps:\n"
            "      - run: bash run.sh --detect\n"
            "      - run: echo 'run.sh --scope static'\n"
            "      - run: bash run.sh --scope tests\n"
        )
        errors: list[str] = []
        self.module.check_ci_uses_runner(errors)
        self.assertTrue(any("forma canonica" in e for e in errors))

    def test_el_parser_lee_los_jobs_y_los_steps(self) -> None:
        self.use_root()
        self._workflow(
            "jobs:\n"
            "  static:\n"
            "    continue-on-error: true\n"
            "    steps:\n"
            "      - name: Detect\n"
            "        run: |\n"
            "          set -eo pipefail\n"
            "          stack=$(bash run.sh --detect)\n"
            "      - name: Gate\n"
            "        run: bash run.sh --scope static\n"
            "  tests:\n"
            "    steps:\n"
            "      - run: bash run.sh --scope tests\n"
        )
        jobs = self.module.parse_workflow_jobs(
            (self.root / ".github" / "workflows" / "qa.yml").read_text(encoding="utf-8")
        )
        self.assertEqual([job["name"] for job in jobs], ["static", "tests"])
        self.assertTrue(jobs[0]["continue_on_error"])
        self.assertFalse(jobs[1]["continue_on_error"])
        self.assertEqual(len(jobs[0]["steps"]), 2)
        # El bloque escalar `run: |` se lee entero, no solo su primera linea.
        self.assertIn("--detect", jobs[0]["steps"][0]["run"])
        self.assertEqual(jobs[0]["steps"][1]["run"], "bash run.sh --scope static")


class TestAgentLinks(ScriptTestCase):
    script = "check-skills.py"

    def _link(self, name: str) -> None:
        links = self.root / ".agents" / "skills"
        links.mkdir(parents=True, exist_ok=True)
        (links / name).symlink_to(self.root / "skills" / name)

    def test_skill_sin_enlace_se_reporta(self) -> None:
        # Una skill que esta en skills/ pero no esta enlazada no la carga
        # ningun agente. Y no hay ninguna senal: el agente no la busca.
        self.use_root()
        write_skill(self.root, "alpha")
        (self.root / ".agents" / "skills").mkdir(parents=True)
        errors: list[str] = []
        self.module.check_agent_links(errors)
        self.assertTrue(any("falta el enlace" in e for e in errors))

    def test_sin_directorio_de_enlaces_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha")
        errors: list[str] = []
        self.module.check_agent_links(errors)
        self.assertTrue(any("falta .agents/skills/" in e for e in errors))

    def test_todas_las_skills_enlazadas_pasan(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha")
        write_skill(self.root, "beta")
        self._link("alpha")
        self._link("beta")
        errors: list[str] = []
        self.module.check_agent_links(errors)
        self.assertEqual(errors, [])

    def test_enlace_a_un_lugar_fuera_del_repo_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha")
        links = self.root / ".agents" / "skills"
        links.mkdir(parents=True, exist_ok=True)
        (links / "alpha").symlink_to(self.root / "otro")
        errors: list[str] = []
        self.module.check_agent_links(errors)
        self.assertTrue(any("fuera de skills/" in e for e in errors))

    def test_enlace_a_skill_inexistente_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha")
        self._link("alpha")
        links = self.root / ".agents" / "skills"
        (links / "fantasma").symlink_to(self.root / "skills" / "fantasma")
        errors: list[str] = []
        self.module.check_agent_links(errors)
        self.assertTrue(any("no corresponde a ninguna skill" in e for e in errors))


class TestReadmeDiagramMatchesChain(ScriptTestCase):
    script = "check-skills.py"

    def _readme(self, diagram: str) -> None:
        (self.root / "README.md").write_text(
            "Intro.\n\n```\n" + diagram + "```\n", encoding="utf-8"
        )

    def _diagram(self, entries: dict[str, set[int]]) -> str:
        lines: list[str] = []
        for phase in sorted({p for phases in entries.values() for p in phases}):
            for skill in sorted(s for s, phases in entries.items() if phase in phases):
                prefix = f"Fase {phase} " if not lines or not lines[-1].startswith("        ") else ""
                lines.append(f"{prefix}{skill}  ← descripcion")
        return "\n".join(lines) + "\n"

    def test_diagrama_alineado_pasa(self) -> None:
        self.use_root()
        entries = {"alpha": {1}, "beta": {2}}
        write_chain(self.root, entries)
        self._readme(self._diagram(entries))
        errors: list[str] = []
        self.module.check_readme_diagram_matches_chain(errors)
        self.assertEqual(errors, [])

    def test_diagrama_desalineado_se_reporta(self) -> None:
        # El diagrama es la cuarta copia del orden. Si deriva sola, el README
        # miente sobre la cadena y nada lo nota.
        self.use_root()
        write_chain(self.root, {"alpha": {1}})
        self._readme("Fase 3  alpha  ← movida de fase\n")
        errors: list[str] = []
        self.module.check_readme_diagram_matches_chain(errors)
        self.assertTrue(any("diagrama" in e for e in errors))

    def test_readme_sin_diagrama_se_reporta(self) -> None:
        self.use_root()
        write_chain(self.root, {"alpha": {1}})
        (self.root / "README.md").write_text("Sin diagrama.\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_readme_diagram_matches_chain(errors)
        self.assertTrue(any("diagrama de fases" in e for e in errors))



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

    def test_fases_coincidentes_pasan(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", phases=(1, 2))
        write_chain(self.root, {"alpha": {1, 2}})
        self._write_agents({"alpha": {1, 2}})
        errors: list[str] = []
        self.module.check_agents_matches_chain(errors)
        self.assertEqual(errors, [])

    def test_fase_desactualizada_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", phases=(1, 2))
        write_chain(self.root, {"alpha": {1, 2}})
        self._write_agents({"alpha": {1}})
        errors: list[str] = []
        self.module.check_agents_matches_chain(errors)
        self.assertTrue(any("pero CHAIN.md le asigna" in e for e in errors))

    def test_skill_faltante_en_agents_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", phases=(1,))
        write_chain(self.root, {"alpha": {1}})
        self._write_agents({})
        errors: list[str] = []
        self.module.check_agents_matches_chain(errors)
        self.assertTrue(any("no tiene una tabla de fases" in e for e in errors))


class TestReadmeListsSkills(ScriptTestCase):
    script = "check-skills.py"

    def test_skill_faltante_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha")
        (self.root / "README.md").write_text(
            "| `skills/otra/` | Otra cosa |\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_readme_lists_skills(errors)
        self.assertTrue(any("no lista la skill 'alpha'" in e for e in errors))

    def test_todas_las_skills_listadas_pasan(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha")
        write_skill(self.root, "beta")
        (self.root / "README.md").write_text(
            "| `skills/alpha/` | A |\n| `skills/beta/` | B |\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_readme_lists_skills(errors)
        self.assertEqual(errors, [])


class TestNoVoseo(ScriptTestCase):
    script = "check-skills.py"

    def test_voseo_se_reporta(self) -> None:
        self.use_root()
        (self.root / "a.md").write_text("Probá esto: querés revisá.\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_no_voseo(errors)
        self.assertEqual(len(errors), 1)
        self.assertIn("voseo rioplatense", errors[0])

    def test_texto_limpio_pasa(self) -> None:
        self.use_root()
        (self.root / "a.md").write_text(
            "Probaste esto: quieres revisar. Está después de las 3, más o menos.\n",
            encoding="utf-8",
        )
        errors: list[str] = []
        self.module.check_no_voseo(errors)
        self.assertEqual(errors, [])

    def test_forma_sin_tilde_no_se_reporta(self) -> None:
        # El voseo de -ar y -er sin tilde se escribe igual que el de "tu".
        # No se puede distinguir, y el checker no lo intenta.
        self.use_root()
        (self.root / "a.md").write_text("podes y tenes\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_no_voseo(errors)
        self.assertEqual(errors, [])

    def test_archivo_exento_no_se_revisa(self) -> None:
        self.use_root()
        exento = self.module.SKILLS_DIR / "fleet-conventions" / "SKILL.md"
        exento.parent.mkdir(parents=True, exist_ok=True)
        exento.write_text("probá, vení, podés\n", encoding="utf-8")
        # VOSEO_EXEMPT se calcula al importar; con use_root() hay que apuntarlo
        # al directorio temporal.
        self.module.VOSEO_EXEMPT = {exento}
        errors: list[str] = []
        self.module.check_no_voseo(errors)
        self.assertEqual(errors, [])


class TestInternalSkills(ScriptTestCase):
    script = "check-skills.py"

    def _write(self, name: str, internal: bool) -> None:
        # El frontmatter se arma a mano: `write_skill` pone el body despues de
        # la seccion "En la cadena", y lo que se prueba aca es el frontmatter.
        meta = "metadata:\n  internal: true\n" if internal else "metadata:\n  hermes:\n    tags: []\n"
        skill_dir = self.root / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            f'---\nname: {name}\ndescription: "{DEFAULT_DESCRIPTION}"\n'
            f"license: MIT\nversion: 1.0.0\n{meta}---\n\nbody\n",
            encoding="utf-8",
        )

    def test_interna_sin_marcar_se_reporta(self) -> None:
        self.use_root()
        self._write("alpha", internal=False)
        self.module.INTERNAL_SKILLS = ["alpha"]
        errors: list[str] = []
        self.module.check_internal_skills(errors)
        self.assertTrue(any("no dice `internal: true`" in e for e in errors))

    def test_publica_marcada_por_error_se_reporta(self) -> None:
        self.use_root()
        self._write("alpha", internal=True)
        self._write("beta", internal=False)
        self.module.INTERNAL_SKILLS = ["beta"]
        errors: list[str] = []
        self.module.check_internal_skills(errors)
        self.assertTrue(any("no esta en INTERNAL_SKILLS" in e for e in errors))

    def test_marcado_correcto_pasa(self) -> None:
        self.use_root()
        self._write("alpha", internal=True)
        self._write("beta", internal=False)
        self.module.INTERNAL_SKILLS = ["alpha"]
        errors: list[str] = []
        self.module.check_internal_skills(errors)
        self.assertEqual(errors, [])


class TestDescriptionsRoute(ScriptTestCase):
    script = "check-skills.py"

    def test_description_sin_ninguna_otra_skill_se_reporta(self) -> None:
        self.use_root()
        # Sin ruteo, dos descriptions matchean el mismo input y el agente no
        # sabe a cual seguir.
        write_skill(self.root, "alpha", description="Hace una cosa. Trigger: cuando A.")
        write_skill(self.root, "beta", description="Hace otra. Trigger: cuando B.")
        errors: list[str] = []
        self.module.check_descriptions_route(errors)
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("no nombra ninguna otra skill" in e for e in errors))

    def test_description_que_nombra_otra_skill_pasa(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", description="Hace una cosa. Trigger: cuando A. NO es B (beta).")
        write_skill(self.root, "beta", description="Hace otra. Trigger: cuando B. NO es A (alpha).")
        errors: list[str] = []
        self.module.check_descriptions_route(errors)
        self.assertEqual(errors, [])


class TestSharedRules(ScriptTestCase):
    script = "check-skills.py"

    def test_regla_ausente_en_un_sitio_se_reporta(self) -> None:
        self.use_root()
        # La regla vive en dos skills. Si una la pierde, el agente recibe dos
        # versiones distintas de lo mismo y nadie lo nota.
        write_skill(self.root, "alpha", body=CANONICAL_RULE)
        write_skill(self.root, "beta", body="nada que ver aca")
        self.module.SHARED_RULES = [
            {
                "name": "el test cambia en el mismo commit",
                "canonical": CANONICAL_RULE,
                "sites": [
                    self.root / "skills" / "alpha" / "SKILL.md",
                    self.root / "skills" / "beta" / "SKILL.md",
                ],
            }
        ]
        errors: list[str] = []
        self.module.check_shared_rules(errors)
        self.assertEqual(len(errors), 1)
        self.assertIn(CANONICAL_RULE, errors[0])

    def test_regla_en_todos_los_sitios_pasa(self) -> None:
        self.use_root()
        write_skill(self.root, "alpha", body=CANONICAL_RULE)
        write_skill(self.root, "beta", body=CANONICAL_RULE)
        self.module.SHARED_RULES = [
            {
                "name": "el test cambia en el mismo commit",
                "canonical": CANONICAL_RULE,
                "sites": [
                    self.root / "skills" / "alpha" / "SKILL.md",
                    self.root / "skills" / "beta" / "SKILL.md",
                ],
            }
        ]
        errors: list[str] = []
        self.module.check_shared_rules(errors)
        self.assertEqual(errors, [])

    def test_la_regla_real_existe_en_los_sitios_declarados(self) -> None:
        # Ver TestSharedRulesOnRealRepo: el chequeo del repo real vive en su
        # propia clase porque `use_root()` muta el modulo y el estado persiste
        # entre tests de la misma clase.
        self.skipTest("cubierto por TestSharedRulesOnRealRepo")


class TestSharedRulesOnRealRepo(ScriptTestCase):
    """Los sitios declarados en SHARED_RULES tienen que existir de verdad."""

    script = "check-skills.py"

    def test_los_sitios_declarados_existen(self) -> None:
        for spec in self.module.SHARED_RULES:
            for site in spec["sites"]:
                rel = site.relative_to(self.module.REPO)
                self.assertTrue(
                    site.is_file(),
                    f"{rel} no existe: SHARED_RULES declara un sitio que no esta",
                )
                content = site.read_text(encoding="utf-8")
                self.assertIn(
                    spec["canonical"],
                    content,
                    f"{rel} no dice la forma canonica de '{spec['name']}'",
                )


class TestReadmeLicenses(ScriptTestCase):
    """La licencia de una skill se declara en tres lugares: frontmatter,
    `upstream/ATTRIBUTION.md` y la seccion de licencia del README.

    El README es la primera copia que se lee y la unica que no se regenera. Si
    lista una skill con la licencia equivocada, el error llega al que instala
    el paquete antes que a nadie.
    """

    script = "check-skills.py"

    def _attribution(self, adapted_rows: str = "") -> None:
        path = self.root / "upstream" / "ATTRIBUTION.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "## Skills propias\n\n"
            "| Skill | Autor | Licencia |\n|---|---|---|\n"
            "| `propia` | Alguien | MIT |\n\n"
            "## Skills adaptadas\n\n"
            "| Skill | Origen | Licencia | Cambios |\n|---|---|---|---|\n"
            + adapted_rows,
            encoding="utf-8",
        )

    def _readme(self, body: str) -> None:
        (self.root / "README.md").write_text(
            f"# Repo\n\n## Licencia\n\n{body}\n", encoding="utf-8"
        )

    def test_licencia_incorrecta_en_el_readme_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "propia", license_="MIT")
        write_skill(self.root, "adaptada", license_="MIT")
        self._attribution("| `adaptada` | Upstream | MIT | algo |\n")
        self._readme("MIT para lo propio. Las adaptadas: Apache-2.0 (`adaptada`).")
        errors: list[str] = []
        self.module.check_readme_licenses(errors)
        self.assertTrue(any("figura con licencia" in e for e in errors))

    def test_skill_adaptada_que_el_readme_omite_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "propia", license_="MIT")
        write_skill(self.root, "adaptada", license_="MIT")
        self._attribution("| `adaptada` | Upstream | MIT | algo |\n")
        self._readme("MIT para lo propio. Las adaptadas: MIT (`otra`).")
        errors: list[str] = []
        self.module.check_readme_licenses(errors)
        self.assertTrue(any("no nombra la skill adaptada 'adaptada'" in e for e in errors))

    def test_skill_inexistente_en_el_readme_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "propia", license_="MIT")
        self._attribution()
        self._readme("MIT para lo propio. Las adaptadas: MIT (`fantasma`).")
        errors: list[str] = []
        self.module.check_readme_licenses(errors)
        self.assertTrue(any("no existe en skills/" in e for e in errors))

    def test_atribucion_contrdice_el_frontmatter_se_reporta(self) -> None:
        self.use_root()
        write_skill(self.root, "adaptada", license_="MIT")
        self._attribution("| `adaptada` | Upstream | Apache-2.0 | algo |\n")
        self._readme("Las adaptadas: MIT (`adaptada`).")
        errors: list[str] = []
        self.module.check_readme_licenses(errors)
        self.assertTrue(any("ATTRIBUTION.md dice Apache-2.0" in e for e in errors))

    def test_todo_alineado_pasa(self) -> None:
        self.use_root()
        write_skill(self.root, "propia", license_="MIT")
        write_skill(self.root, "adaptada", license_="MIT")
        write_skill(self.root, "apache", license_="Apache-2.0")
        self._attribution(
            "| `adaptada` | Upstream | MIT | algo |\n"
            "| `apache` | Upstream | Apache-2.0 | algo |\n"
        )
        self._readme(
            "MIT para lo propio. Las adaptadas: MIT (`adaptada`) y "
            "Apache-2.0 (`apache`)."
        )
        errors: list[str] = []
        self.module.check_readme_licenses(errors)
        self.assertEqual(errors, [])


class TestSkillReferences(ScriptTestCase):
    """Toda skill que un SKILL.md nombra como ruteo tiene que existir.

    `CHAIN.md` no se carga por description: en runtime lo unico que decide que
    skill entra es el texto de la description y los ruteos del cuerpo. Un
    nombre que no existe es una promesa que el agente no puede cumplir, y lo
    busca adentro del repo.
    """

    script = "check-skills.py"

    def _skill(self, name: str, frontmatter_extra: str = "", body: str = "") -> None:
        skill_dir = self.root / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            f"name: {name}\n"
            f'description: "{DEFAULT_DESCRIPTION}"\n'
            "license: MIT\n"
            "version: 1.0.0\n"
            f"{frontmatter_extra}"
            "---\n\n"
            f"# {name}\n\n"
            "## En la cadena\n\nFase 1 — Diseno. Cuando toque.\n\n"
            f"{body}\n",
            encoding="utf-8",
        )

    def test_related_skills_inexistente_se_reporta(self) -> None:
        self.use_root()
        self._skill("alpha", "metadata:\n  related_skills: [fantasma]\n")
        errors: list[str] = []
        self.module.check_skill_references(errors)
        self.assertTrue(any("related_skills" in e and "fantasma" in e for e in errors))

    def test_related_skills_existente_pasa(self) -> None:
        self.use_root()
        self._skill("alpha")
        self._skill("beta", "metadata:\n  related_skills: [alpha]\n")
        errors: list[str] = []
        self.module.check_skill_references(errors)
        self.assertEqual(errors, [])

    def test_ruteo_por_flecha_a_skill_inexistente_se_reporta(self) -> None:
        self.use_root()
        self._skill("alpha", body="No usar para esto (→ `fantasma`).")
        errors: list[str] = []
        self.module.check_skill_references(errors)
        self.assertTrue(any("fantasma" in e for e in errors))

    def test_skill_externa_sin_descargo_se_reporta(self) -> None:
        self.use_root()
        self._skill("alpha", body="No usar para esto (→ `agent-stack-footprint-audit`).")
        errors: list[str] = []
        self.module.check_skill_references(errors)
        self.assertTrue(any("externa" in e for e in errors))

    def test_skill_externa_con_descargo_pasa(self) -> None:
        self.use_root()
        self._skill(
            "alpha",
            body=(
                "No usar para esto (→ `agent-stack-footprint-audit`).\n"
                "Esa es externa a este repo: usala solo si esta instalada.\n"
            ),
        )
        errors: list[str] = []
        self.module.check_skill_references(errors)
        self.assertEqual(errors, [])

    def test_ruteo_en_la_description_a_skill_inexistente_se_reporta(self) -> None:
        self.use_root()
        self._skill("alpha")
        path = self.root / "skills" / "alpha" / "SKILL.md"
        content = path.read_text(encoding="utf-8").replace(
            DEFAULT_DESCRIPTION,
            "Hace una cosa. Trigger: siempre. NOT lo otro (fantasma).",
        )
        path.write_text(content, encoding="utf-8")
        errors: list[str] = []
        self.module.check_skill_references(errors)
        self.assertTrue(any("fantasma" in e for e in errors))

    def test_ruteo_en_la_description_a_skill_existente_pasa(self) -> None:
        self.use_root()
        self._skill("alpha")
        self._skill("beta")
        path = self.root / "skills" / "alpha" / "SKILL.md"
        content = path.read_text(encoding="utf-8").replace(
            DEFAULT_DESCRIPTION,
            "Hace una cosa. Trigger: siempre. NOT lo otro (beta).",
        )
        path.write_text(content, encoding="utf-8")
        errors: list[str] = []
        self.module.check_skill_references(errors)
        self.assertEqual(errors, [])


class TestReadmeCheckCount(ScriptTestCase):
    """El README dice cuantos checks tiene el checker: que diga la verdad.

    El numero se cuenta sobre el codigo de `main()`, no sobre una lista escrita
    a mano: la lista seria otra copia que deriva sola.
    """

    script = "check-skills.py"

    def test_cuenta_distinta_se_reporta(self) -> None:
        self.use_root()
        real = self.module.count_checks()
        (self.root / "README.md").write_text(
            f"`check-skills.py` | {real + 3} checks: lo que sea.\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_readme_check_count(errors)
        self.assertTrue(any("checks" in e for e in errors))

    def test_cuenta_correcta_pasa(self) -> None:
        self.use_root()
        real = self.module.count_checks()
        (self.root / "README.md").write_text(
            f"`check-skills.py` | {real} checks: lo que sea.\n", encoding="utf-8"
        )
        errors: list[str] = []
        self.module.check_readme_check_count(errors)
        self.assertEqual(errors, [])

    def test_readme_sin_el_numero_se_reporta(self) -> None:
        self.use_root()
        (self.root / "README.md").write_text("`check-skills.py` | el validador.\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_readme_check_count(errors)
        self.assertTrue(any("no dice cuantos checks" in e for e in errors))

    def test_el_conteo_sale_del_codigo(self) -> None:
        # El numero viene de las llamadas en main(), no de una constante.
        source = "def main() -> int:\n    check_a(errors)\n    check_b(errors)\n    check_a(errors)\n"
        self.assertEqual(self.module.count_checks(source), 2)


class TestSkillPaths(ScriptTestCase):
    """Un path que una skill nombra tiene que existir.

    `scripts/run.sh` dentro de un SKILL.md es relativo a la skill: el agente lo
    resuelve desde ahi. Un path del repo se nombra con el prefijo `repo/`, para
    que la ambiguedad no dependa de donde se mire.
    """

    script = "check-skills.py"

    def _skill(self, name: str, body: str = "", files: tuple[str, ...] = ()) -> None:
        skill_dir = self.root / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            f"name: {name}\n"
            f'description: "{DEFAULT_DESCRIPTION}"\n'
            "license: MIT\n"
            "version: 1.0.0\n"
            "---\n\n"
            f"# {name}\n\n"
            "## En la cadena\n\nFase 1 — Diseno. Cuando toque.\n\n"
            f"{body}\n",
            encoding="utf-8",
        )
        for rel in files:
            target = skill_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("contenido\n", encoding="utf-8")

    def test_path_de_skill_inexistente_se_reporta(self) -> None:
        self.use_root()
        self._skill("alpha", "El runner es `scripts/run.sh`.")
        errors: list[str] = []
        self.module.check_skill_paths(errors)
        self.assertTrue(any("scripts/run.sh" in e for e in errors))

    def test_path_de_skill_existente_pasa(self) -> None:
        self.use_root()
        self._skill("alpha", "El runner es `scripts/run.sh`.", ("scripts/run.sh",))
        errors: list[str] = []
        self.module.check_skill_paths(errors)
        self.assertEqual(errors, [])

    def test_path_con_prefijo_de_repo_se_verifica_en_el_repo(self) -> None:
        self.use_root()
        self._skill("alpha", "El checker es `repo/scripts/check-skills.py`.")
        errors: list[str] = []
        self.module.check_skill_paths(errors)
        self.assertTrue(any("repo/scripts/check-skills.py" in e for e in errors))

    def test_path_de_repo_existente_pasa(self) -> None:
        self.use_root()
        self._skill("alpha", "El checker es `repo/scripts/check-skills.py`.")
        (self.root / "scripts").mkdir(parents=True)
        (self.root / "scripts" / "check-skills.py").write_text("x\n", encoding="utf-8")
        errors: list[str] = []
        self.module.check_skill_paths(errors)
        self.assertEqual(errors, [])

    def test_link_markdown_roto_se_reporta(self) -> None:
        self.use_root()
        self._skill("alpha", "Mira [`fantasma.md`](fantasma.md).")
        errors: list[str] = []
        self.module.check_skill_paths(errors)
        self.assertTrue(any("fantasma.md" in e for e in errors))

    def test_link_markdown_a_skill_hermana_pasa(self) -> None:
        self.use_root()
        self._skill("alpha")
        self._skill("beta")
        (self.root / "skills" / "alpha" / "SKILL.md").write_text(
            "---\n"
            "name: alpha\n"
            f'description: "{DEFAULT_DESCRIPTION}"\n'
            "license: MIT\n"
            "version: 1.0.0\n"
            "---\n\n"
            "# alpha\n\n"
            "## En la cadena\n\nFase 1 — Diseno. Cuando toque.\n\n"
            "Mira [`beta`](../beta/SKILL.md).\n",
            encoding="utf-8",
        )
        errors: list[str] = []
        self.module.check_skill_paths(errors)
        self.assertEqual(errors, [])


class TestDescriptionContract(ScriptTestCase):
    """Cada description dice que hace, cuando aplica y a quien cede el caso que
    no es suyo.

    El formato esta documentado en `upstream/ATTRIBUTION.md`. No es estetica:
    `CHAIN.md` no se carga por description, asi que la description es el unico
    mecanismo de ruteo que existe en runtime.
    """

    script = "check-skills.py"

    def _skill(self, name: str, description: str) -> None:
        skill_dir = self.root / "skills" / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            f"name: {name}\n"
            f'description: "{description}"\n'
            "license: MIT\n"
            "version: 1.0.0\n"
            "---\n\n"
            f"# {name}\n\n"
            "## En la cadena\n\nFase 1 — Diseno. Cuando toque.\n",
            encoding="utf-8",
        )

    def test_description_sin_trigger_se_reporta(self) -> None:
        self.use_root()
        self._skill("alpha", "Hace una cosa. NOT lo otro (beta).")
        errors: list[str] = []
        self.module.check_description_contract(errors)
        self.assertTrue(any("Trigger:" in e for e in errors))

    def test_description_sin_not_se_reporta(self) -> None:
        self.use_root()
        self._skill("alpha", "Hace una cosa. Trigger: siempre.")
        errors: list[str] = []
        self.module.check_description_contract(errors)
        self.assertTrue(any("cede el caso" in e for e in errors))

    def test_description_completa_pasa(self) -> None:
        self.use_root()
        self._skill("alpha", "Hace una cosa. Trigger: siempre. NOT lo otro (beta).")
        errors: list[str] = []
        self.module.check_description_contract(errors)
        self.assertEqual(errors, [])


class TestCoverageConsistency(ScriptTestCase):
    script = "check-skills.py"

    def test_cjk_y_fences_miran_el_mismo_conjunto(self) -> None:
        self.use_root()
        # Un archivo con las dos fallas: los dos chequeos tienen que reportarlo.
        # Antes uno miraba los trackeados y el otro todo el directorio.
        (self.root / "a.md").write_text(
            "texto \u6b63\u5e38\n```python\nsin cerrar\n", encoding="utf-8"
        )
        cjk_errors: list[str] = []
        self.module.check_cjk(cjk_errors)
        fence_errors: list[str] = []
        self.module.check_fences(fence_errors)
        self.assertTrue(any("glifos CJK" in e for e in cjk_errors))
        self.assertTrue(any("nunca se cierra" in e for e in fence_errors))


if __name__ == "__main__":
    unittest.main()
