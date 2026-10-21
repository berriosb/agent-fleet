#!/usr/bin/env bash
# scripts/release.sh — publica el tag v1.
#
# Por que existe
# ──────────────
# Los repos consumidores invocan este repo asi:
#
#     uses: berriosb/agent-fleet/.github/workflows/qa.yml@v1
#
# y ese workflow hace checkout del runner en `ref: v1`. O sea: el tag v1 ES
# la release. Si el tag no se mueve junto con el runner, la CI de los
# consumidores sigue corriendo el runner viejo: los arreglos al gate no llegan
# y el fallo aparece en el repo de otro, semanas despues.
#
# El tag estuvo 13 commits atrasado sin que nada lo dijera. Ahora lo dice la
# CI (job `tag-drift`) y lo mueve este script.
#
# Que hace
# ───────
# 1. Verifica que el working tree este limpio.
# 2. Corre la verificacion del repo.
# 3. Mueve el tag v1 al HEAD actual, anotado.
# 4. Con `--push`, lo publica. Sin `--push`, deja el tag local: publicar es una
#    accion explicita, no un efecto secundario de un commit.
#
# Uso
# ───
#   ./scripts/release.sh          # prepara el tag local
#   ./scripts/release.sh --push   # lo publica en el remoto
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

TAG="v1"
PUSH=0
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --push) PUSH=1 ;;
    --force) FORCE=1 ;;
    -h|--help)
      echo "usage: release.sh [--push] [--force]"
      echo "  (sin flags)  deja el tag v1 en HEAD, local."
      echo "  --push       publica el tag en el remoto."
      echo "  --force      mueve el tag aunque no sea hacia adelante."
      exit 0
      ;;
    *)
      echo "==> [release] ERROR: argumento desconocido '$arg' (usar --push)" >&2
      exit 2
      ;;
  esac
done

echo "==> [release] 1/4 Working tree limpio..."
if [ -n "$(git status --porcelain)" ]; then
  echo "==> [release] ERROR: hay cambios sin commitear. Commitea antes de publicar." >&2
  git status --short >&2
  exit 1
fi

echo "==> [release] 2/4 Verificacion del repo..."
./scripts/verify.sh

echo "==> [release] 3/4 Moviendo el tag $TAG..."
HEAD_COMMIT="$(git rev-parse HEAD)"
HEAD_SHORT="$(git rev-parse --short HEAD)"

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
  PREVIOUS="$(git rev-list -n 1 "$TAG")"
  if [ "$PREVIOUS" = "$HEAD_COMMIT" ]; then
    echo "==> [release] El tag $TAG ya apunta a $HEAD_SHORT. Nada que hacer."
    exit 0
  fi
  # El tag solo avanza. Sin este guard, dos pushes seguidos a main pueden dejar
  # el tag en el commit viejo: el run que tarda mas empuja despues y lo
  # atrasa. Con --force se puede mover a proposito hacia atras.
  if [ "$FORCE" -eq 0 ] && ! git merge-base --is-ancestor "$PREVIOUS" HEAD 2>/dev/null; then
    echo "==> [release] El tag $TAG esta adelante de HEAD ($(git rev-parse --short "$PREVIOUS"))." >&2
    echo "    No se mueve hacia atras. Con --force se fuerza." >&2
    exit 0
  fi
  echo "    $TAG: $(git rev-parse --short "$PREVIOUS") -> $HEAD_SHORT"
else
  echo "    $TAG no existe todavia: se crea en $HEAD_SHORT"
fi

git tag -f -a "$TAG" -m "agent-fleet $TAG: $(git log -1 --format=%s HEAD)"

echo "==> [release] 4/4 Publicando..."
if [ "$PUSH" -eq 1 ]; then
  # Un tag se mueve con --force: el remoto no acepta mover tags sin force.
  git push origin "refs/tags/$TAG" --force
  echo "==> [release] Tag $TAG publicado en $(git remote get-url origin)."
else
  echo "==> [release] Tag $TAG creado localmente en $HEAD_SHORT."
  echo "    Publicalo con: git push origin refs/tags/$TAG --force"
fi
