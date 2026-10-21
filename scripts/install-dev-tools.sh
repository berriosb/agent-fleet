#!/usr/bin/env bash
# scripts/install-dev-tools.sh — instala las herramientas de QA del repo.
#
# Por que existe
# ──────────────
# Las herramientas de QA estaban declaradas de a una, en el workflow de CI. La
# consecuencia: la CI corria `mypy` y la maquina local no, y el typecheck
# local se reportaba como omitido. El gate decia una cosa en un lado y otra en
# el otro.
#
# La declaracion vive en `requirements-dev.txt`: es el unico lugar donde se dice
# que herramientas hacen falta, y los dos caminos lo leen de ahi.
#
# Con uv, cada herramienta se instala como tool aislada (`uv tool install` toma
# un solo paquete por vez), asi que el runner las encuentra en el PATH sin
# necesidad de un venv. Con pip, es un solo comando:
#
#     pip install -r requirements-dev.txt
#
# Uso
# ───
#   ./scripts/install-dev-tools.sh
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

REQ="requirements-dev.txt"
if [ ! -f "$REQ" ]; then
  echo "==> [dev-tools] ERROR: falta $REQ" >&2
  exit 1
fi

# Solo las lineas con nombre de paquete: se ignoran comentarios y vacias.
PACKAGES="$(grep -vE '^\s*(#|$)' "$REQ" | tr '\n' ' ')"
if [ -z "${PACKAGES// /}" ]; then
  echo "==> [dev-tools] ERROR: $REQ no declara ninguna herramienta" >&2
  exit 1
fi

if command -v uv >/dev/null 2>&1; then
  for pkg in $PACKAGES; do
    echo "==> [dev-tools] instalando $pkg (uv tool)..."
    uv tool install "$pkg"
  done
elif command -v pip >/dev/null 2>&1; then
  echo "==> [dev-tools] instalando con pip..."
  pip install -r "$REQ"
else
  echo "==> [dev-tools] ERROR: no hay ni uv ni pip en el PATH." >&2
  echo "    Instalalas a mano: $PACKAGES" >&2
  exit 1
fi

echo "==> [dev-tools] listo:"
for pkg in $PACKAGES; do
  if command -v "$pkg" >/dev/null 2>&1; then
    echo "    $pkg: $(command -v "$pkg")"
  else
    echo "    $pkg: NO ENCONTRADO en el PATH" >&2
  fi
done
