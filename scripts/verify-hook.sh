#!/usr/bin/env bash
# scripts/verify-hook.sh — round-trip del gate de push.
#
# Por que existe
# ──────────────
# El gate de pre-push-qa tiene dos piezas: el runner (produce el marcador) y el hook
# (lo consume y decide). El runner se ejecutaba en verify.sh, pero el hook nunca se
# probaba. Una regresion en el protocolo del marcador — que es lo que realmente
# bloquea un push roto — pasaba sin avisar.
#
# Que prueba
# ─────────
# 1. marcador con el hash de HEAD  -> el hook permite el push.
# 2. el marcador se consume        -> una aprobacion vieja no se puede reusar.
# 3. marcador con otro hash        -> el hook bloquea (STALE MARKER).
# 4. sin marcador                  -> el hook bloquea.
#
# El hook se invoca directo (no se hace push). PRE_PUSH_QA_PATHS se fija al repo actual
# para que la allowlist de rutas lo aplique aqui: en CI el checkout vive fuera de los
# prefijos que el hook reconoce, y sin esto el test pasaria sin probar nada.

set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

HOOK="$REPO_ROOT/skills/pre-push-qa/examples/pre-push.sh"
GIT_DIR="$(git rev-parse --git-dir)"
MARKER="$GIT_DIR/pre-push-qa-ok"
HEAD_HASH="$(git rev-parse HEAD)"
export PRE_PUSH_QA_PATHS="$REPO_ROOT"

FAILED=0

cleanup() { rm -f "$MARKER" 2>/dev/null || true; }
trap cleanup EXIT

run_hook() {
  # El hook se ejecuta como proceso aparte: nunca se hace push de verdad.
  bash "$HOOK" origin HEAD:refs/heads/verify-selftest < /dev/null > /dev/null 2>&1
}

if [ ! -f "$HOOK" ]; then
  echo "ERROR: no se encontró el hook en $HOOK" >&2
  exit 1
fi

# 1. Marcador válido -> permitido.
echo "$(git rev-parse HEAD)" > "$MARKER"
if run_hook; then
  echo "    OK: hook acepta un marcador que coincide con HEAD"
else
  echo "    ERROR: hook rechazó un marcador válido (exit distinto de 0)" >&2
  FAILED=1
fi

# 2. El marcador se consume en el push.
if [ -f "$MARKER" ]; then
  echo "    ERROR: el hook no consumió el marcador; una aprobación vieja se podría reusar" >&2
  FAILED=1
else
  echo "    OK: el marcador se consume al validar el push"
fi

# 3. Marcador obsoleto -> bloqueado.
echo "0000000000000000000000000000000000000000" > "$MARKER"
if run_hook; then
  echo "    ERROR: el hook aceptó un marcador de otro commit (STALE MARKER no detectado)" >&2
  FAILED=1
else
  echo "    OK: el hook bloquea un marcador obsoleto"
fi
rm -f "$MARKER" 2>/dev/null || true

# 4. Sin marcador -> bloqueado.
if run_hook; then
  echo "    ERROR: el hook permitió un push sin marcador de verificación" >&2
  FAILED=1
else
  echo "    OK: el hook bloquea un push sin verificación"
fi

exit "$FAILED"
