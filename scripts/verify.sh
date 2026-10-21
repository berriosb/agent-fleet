#!/usr/bin/env bash
# scripts/verify.sh — Verificación del repo de agent-fleet.
#
# Alcance: ESTE REPO. Lo que se verifica acá es el contenido del repo, y no
# depende de la maquina donde corre. Por eso es lo que corre la CI, y por eso
# da el mismo resultado en un clone limpio y en la workstation.
#
# El estado de la MAQUINA (las skills enlazadas en ~/.agents, ~/.claude,
# ~/.codex, ~/.gemini, y las copias divergentes en los perfiles de Hermes) es
# otra verificacion, distinta: vive en `scripts/check-install.py` y se corre
# aparte, o con `--install` en este script. Mezclar las dos cosas hacia que
# `verify.sh` fallara en una maquina sin instalar las skills, y pasara en CI
# sin decir por que.
#
#   1. El vault proyecta igual a references/vault-conventions.md
#   2. Frontmatter, CJK, fences, flags replicados y consistencia de la cadena
#   3. El hook de push acepta, consume y bloquea como debe
#   4. El runner de pre-push-qa pasa sobre el repo
#
# Uso:
#   ./scripts/verify.sh              # solo el repo: hermetico
#   ./scripts/verify.sh --install    # el repo + el estado de esta maquina
#
# Todo lo que corre acá es stdlib + bash: no se instala nada. La logica de
# validacion vive en scripts/check-skills.py, que tambien usa CI, para que
# local y remoto apliquen exactamente los mismos criterios.
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

WITH_INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --install) WITH_INSTALL=1 ;;
    -h|--help)
      echo "usage: verify.sh [--install]"
      echo "  (sin flags)  verifica el repo. Es lo que corre la CI."
      echo "  --install    verifica ademas el estado de esta maquina."
      exit 0
      ;;
    *)
      echo "==> [verify] ERROR: argumento desconocido '$arg' (usar --install)" >&2
      exit 2
      ;;
  esac
done

echo "==> [verify] 1/4 Sincronización de convenciones con el vault..."
python3 scripts/sync-conventions.py --check

echo "==> [verify] 2/4 Frontmatter, CJK, fences y consistencia de la cadena..."
python3 scripts/check-skills.py

echo "==> [verify] 3/4 Round-trip del hook de push..."
bash scripts/verify-hook.sh

echo "==> [verify] 4/4 Runner de pre-push-qa sobre el repo..."
./skills/pre-push-qa/scripts/run.sh

if [ "$WITH_INSTALL" -eq 1 ]; then
  echo
  echo "==> [verify] + Estado de instalación en esta máquina..."
  python3 scripts/check-install.py
fi

echo
echo "==> [verify] OK — todo verificado."
