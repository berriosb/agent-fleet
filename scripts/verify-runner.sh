#!/usr/bin/env bash
# scripts/verify-runner.sh — round-trip del runner de pre-push-qa.
#
# Por que existe
# ──────────────
# `scripts/verify-hook.sh` prueba el hook. El runner —la pieza que de verdad
# decide si un push pasa— no tenia ninguna prueba, y ya se rompió una vez:
# cuando una herramienta no estaba instalada, el gate la tomaba por un chequeo
# fallido y rechazaba el push. El mismo repo pasaba en una maquina con mypy y
# fallaba en otra sin el.
#
# Que prueba
# ─────────
# 1. Una herramienta ausente se OMITE. El gate bloquea por las herramientas que
#    estan y encuentran problemas, nunca por las que el proyecto no declaro.
# 2. Un `.env` trackeado BLOQUEA el push (chequeo de seguridad).
# 3. `--detect` imprime el stack detectado.
# 4. `--scope static|tests` reparte los chequeos y NO escribe el marcador: un
#    run parcial no aprueba ningun push.
# 5. Un scope invalido se rechaza con codigo 2.
#
# El caso 1 se prueba con un PATH minimo: los binarios de coreutils que el
# runner necesita y nada mas. Asi el resultado no depende de lo que tenga
# instalado la maquina donde corre el test.
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
RUNNER="$REPO_ROOT/skills/pre-push-qa/scripts/run.sh"
FAILED=0

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# ── PATH minimo ──────────────────────────────────────────────────────────────────
# Todo de /usr/bin y /bin, menos las herramientas de QA y los runtimes. Asi se
# simula una maquina donde el proyecto no declara ninguna.
MIN_BIN="$WORK/bin"
mkdir -p "$MIN_BIN"
for dir in /usr/bin /bin; do
  [ -d "$dir" ] || continue
  for exe in "$dir"/*; do
    [ -e "$exe" ] || continue
    name="$(basename "$exe")"
    case "$name" in
      ruff|mypy|pytest|uvx|python|python[0-9]*|node|npm|npx|pnpm|yarn|bun|tsc|shellcheck|terraform|hadolint)
        continue
        ;;
    esac
    [ -e "$MIN_BIN/$name" ] || ln -s "$exe" "$MIN_BIN/$name" 2>/dev/null || true
  done
done

# uv se deja en el PATH minimo cuando existe: el caso de un repo CON
# manifiesto usa `uv run <tool>`, y ahi esta el bug que se quiere cubrir.
if command -v uv >/dev/null 2>&1; then
  ln -s "$(command -v uv)" "$MIN_BIN/uv" 2>/dev/null || true
fi

# ── Fixtures ────────────────────────────────────────────────────────────────────
PY_REPO="$WORK/pyrepo"
mkdir -p "$PY_REPO"
(
  cd "$PY_REPO"
  git init -q
  printf 'def f(x):\n    return x\n' > app.py
  printf '# Fixture\n' > README.md
  git add -A
  git -c user.email=t@t -c user.name=t commit -qm init
)

# Mismo repo, pero CON manifiesto: dispara el camino `uv run <tool>`, que es
# donde una herramienta ausente se confundia con un chequeo fallido.
UV_REPO="$WORK/uvrepo"
mkdir -p "$UV_REPO"
(
  cd "$UV_REPO"
  git init -q
  printf '[project]\nname = "fixture"\nversion = "0.1.0"\nrequires-python = ">=3.9"\ndependencies = []\n' > pyproject.toml
  printf 'def f(x):\n    return x\n' > app.py
  git add -A
  git -c user.email=t@t -c user.name=t commit -qm init
)

ENV_REPO="$WORK/envrepo"
mkdir -p "$ENV_REPO"
(
  cd "$ENV_REPO"
  git init -q
  printf 'SECRET=valor\n' > .env
  git add -A -f
  git -c user.email=t@t -c user.name=t commit -qm init
)

run_gate() {
  # Corre el runner con el PATH minimo, en el repo indicado.
  local dir="$1"; shift
  ( cd "$dir" && env PATH="$MIN_BIN" bash "$RUNNER" "$@" )
}

echo "    gate: una herramienta ausente se omite, no falla..."
if OUT="$(run_gate "$PY_REPO" 2>&1)"; then
  if echo "$OUT" | grep -q "Skipping python lint"; then
    echo "    OK: sin herramientas, el gate omite y aprueba"
  else
    echo "    ERROR: se esperaba 'Skipping python lint' en la salida" >&2
    echo "$OUT" | sed 's/^/      /' >&2
    FAILED=1
  fi
else
  echo "    ERROR: el gate fallo con un proyecto sin herramientas declaradas" >&2
  echo "$OUT" | sed 's/^/      /' >&2
  FAILED=1
fi

echo "    gate: un .env trackeado bloquea el push..."
if run_gate "$ENV_REPO" >/dev/null 2>&1; then
  echo "    ERROR: el gate aprobo un push con un .env trackeado" >&2
  FAILED=1
else
  echo "    OK: el .env trackeado bloquea el push"
fi

if [ -x "$MIN_BIN/uv" ]; then
  echo "    gate: repo con manifiesto y sin herramientas (uv run)..."
  if OUT="$(run_gate "$UV_REPO" 2>&1)"; then
    echo "    OK: con uv, las herramientas ausentes se omiten y el gate aprueba"
  else
    echo "    ERROR: con uv, el gate fallo por una herramienta ausente" >&2
    echo "$OUT" | sed 's/^/      /' >&2
    FAILED=1
  fi
else
  echo "    SKIP: uv no esta en esta maquina; el caso con manifiesto no se prueba"
fi

echo "    runner: --detect imprime el stack..."
STACK="$(run_gate "$PY_REPO" --detect 2>/dev/null | tail -1)"
if [ "$STACK" = "python" ]; then
  echo "    OK: --detect -> python"
else
  echo "    ERROR: --detect devolvio '$STACK', se esperaba 'python'" >&2
  FAILED=1
fi

echo "    runner: --detect reconoce go y cargo..."
GO_REPO="$WORK/gorepo"
mkdir -p "$GO_REPO"
(
  cd "$GO_REPO"
  git init -q
  printf 'module ejemplo\n\ngo 1.21\n' > go.mod
  printf 'package main\n\nfunc main() {}\n' > main.go
  git add -A
  git -c user.email=t@t -c user.name=t commit -qm init
)
CARGO_REPO="$WORK/cargorepo"
mkdir -p "$CARGO_REPO"
(
  cd "$CARGO_REPO"
  git init -q
  printf '[package]\nname = "ejemplo"\nversion = "0.1.0"\nedition = "2021"\n' > Cargo.toml
  git add -A
  git -c user.email=t@t -c user.name=t commit -qm init
)
for pair in "$GO_REPO:go" "$CARGO_REPO:cargo"; do
  dir="${pair%%:*}"
  expected="${pair##*:}"
  got="$(run_gate "$dir" --detect 2>/dev/null | tail -1)"
  if [ "$got" = "$expected" ]; then
    echo "    OK: --detect -> $expected"
  else
    echo "    ERROR: --detect devolvio '$got', se esperaba '$expected'" >&2
    FAILED=1
  fi
done

if command -v pytest >/dev/null 2>&1; then
  echo "    gate: los fallos preexistentes no bloquean, los nuevos si..."
  # Fixture: un repo Python con un test que falla, y lint limpio para que lo
  # que se prova sea el baseline y no otra cosa.
  BL_REPO="$WORK/blrepo"
  mkdir -p "$BL_REPO"
  (
    cd "$BL_REPO"
    git init -q
    printf 'def test_roto():\n    value = 1\n    assert value == 2\n' > test_algo.py
    git add -A
    git -c user.email=t@t -c user.name=t commit -qm init
  )

  # 1. Sin baseline, un test roto bloquea.
  if ( cd "$BL_REPO" && bash "$RUNNER" --scope tests >/dev/null 2>&1 ); then
    echo "    ERROR: el gate aprobo un test roto sin baseline" >&2
    FAILED=1
  else
    echo "    OK: sin baseline, el test roto bloquea"
  fi

  # 2. Con el baseline que lo incluye, el mismo fallo no bloquea.
  ( cd "$BL_REPO" && bash "$RUNNER" --scope tests --update-baseline >/dev/null 2>&1 ) || true
  if ( cd "$BL_REPO" && bash "$RUNNER" --scope tests >/dev/null 2>&1 ); then
    echo "    OK: con el baseline, el fallo preexistente no bloquea"
  else
    echo "    ERROR: el gate bloqueo un fallo que estaba en el baseline" >&2
    FAILED=1
  fi

  # 3. Con un baseline que NO lo incluye, el fallo vuelve a bloquear.
  printf '# baseline\n\nFAILED test_algo.py::test_otro\n' > "$BL_REPO/pre-push-qa-baseline.txt"
  if ( cd "$BL_REPO" && bash "$RUNNER" --scope tests >/dev/null 2>&1 ); then
    echo "    ERROR: el gate aprobo un fallo nuevo con baseline" >&2
    FAILED=1
  else
    echo "    OK: un fallo nuevo bloquea aunque haya baseline"
  fi
else
  echo "    SKIP: pytest no esta en esta maquina; los casos de baseline no se prueban"
fi

echo "    runner: un scope parcial no escribe el marcador..."
MARKER="$PY_REPO/.git/pre-push-qa-ok"
rm -f "$MARKER"
run_gate "$PY_REPO" --scope static >/dev/null 2>&1 || true
if [ -f "$MARKER" ]; then
  echo "    ERROR: --scope static escribio el marcador; un run parcial no aprueba un push" >&2
  FAILED=1
else
  echo "    OK: --scope static no escribe marcador"
fi

echo "    runner: un scope invalido se rechaza..."
if run_gate "$PY_REPO" --scope bogus >/dev/null 2>&1; then
  echo "    ERROR: el runner acepto un scope invalido" >&2
  FAILED=1
else
  CODE=$?
  if [ "$CODE" -eq 2 ]; then
    echo "    OK: scope invalido -> codigo 2"
  else
    echo "    ERROR: scope invalido devolvio codigo $CODE, se esperaba 2" >&2
    FAILED=1
  fi
fi

exit "$FAILED"
