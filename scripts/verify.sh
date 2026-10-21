#!/usr/bin/env bash
# scripts/verify.sh — Verificación consolidada de agent-fleet.
#
# Todo lo que corre acá es stdlib + bash: no se instala nada. La lógica de validación
# vive en scripts/check-skills.py y scripts/check-install.py, que también usa CI, así
# que local y remoto aplican exactamente los mismos criterios.
#
#   1. El vault proyecta igual a references/vault-conventions.md
#   2. Frontmatter, CJK, fences y patrones consistentes
#   3. Las skills están enlazadas donde los agentes las buscan
#   4. El runner de pre-push-qa pasa
#   5. El hook de push acepta, consume y bloquea como debe
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

echo "==> [verify] 1/5 Sincronización de convenciones con el vault..."
python3 scripts/sync-conventions.py --check

echo "==> [verify] 2/5 Frontmatter, CJK, fences y consistencia de patrones..."
python3 scripts/check-skills.py

echo "==> [verify] 3/5 Enlaces de skills en los directorios de agente..."
python3 scripts/check-install.py

echo "==> [verify] 4/5 Runner de pre-push-qa..."
./skills/pre-push-qa/scripts/run.sh

echo "==> [verify] 5/5 Round-trip del hook de push..."
bash scripts/verify-hook.sh

echo
echo "==> [verify] OK — todo verificado."
