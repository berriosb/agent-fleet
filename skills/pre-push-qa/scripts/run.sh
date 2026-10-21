#!/usr/bin/env bash
# scripts/run.sh — Local QA gate execution script for pre-push checks.
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

# ── Argumentos ───────────────────────────────────────────────────────────────────
# `--scope` reparte el gate: la CI corre la parte estatica y la de tests en jobs
# separados, pero las dos ejecutan ESTE script. Es la unica implementacion de la
# deteccion de stack y de los comandos; la CI no tiene una copia que pueda
# divergir.
#
#   all     (default) lint + tipos + tests + build
#   static            lint + tipos + build
#   tests             tests
#
# `--detect` imprime el stack detectado y sale. La CI lo usa para decidir que
# pasos de setup correr, sin tener su propia deteccion.
SCOPE="all"
DETECT_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --scope)
      SCOPE="${2:-}"
      shift 2 || true
      ;;
    --scope=*)
      SCOPE="${1#*=}"
      shift
      ;;
    --detect)
      DETECT_ONLY=1
      shift
      ;;
    -h|--help)
      echo "usage: run.sh [--scope all|static|tests] [--detect]"
      exit 0
      ;;
    *)
      echo "==> [pre-push-qa] ERROR: argumento desconocido '$1'" >&2
      echo "    usage: run.sh [--scope all|static|tests] [--detect]" >&2
      exit 2
      ;;
  esac
done

case "$SCOPE" in
  all|static|tests) ;;
  *)
    echo "==> [pre-push-qa] ERROR: scope invalido '$SCOPE' (se espera all, static o tests)" >&2
    exit 2
    ;;
esac

echo "==> [pre-push-qa] Detecting repository stack..."

has_code_files() {
  find . -maxdepth 4 -type f \( \
    -name "*.js" -o -name "*.ts" -o -name "*.jsx" -o -name "*.tsx" -o \
    -name "*.py" -o -name "*.go" -o -name "*.rs" -o -name "*.sh" -o \
    -name "*.tf" -o -name "Dockerfile*" -o -name "*.c" -o -name "*.cpp" -o \
    -name "*.java" -o -name "*.rb" -o -name "*.php" \
  \) -not -path "*/.*" -not -path "*node_modules*" -not -path "*vendor*" -not -path "*.venv*" -print -quit | grep -q .
}

has_python_files() {
  find . -maxdepth 4 -type f -name "*.py" \
    -not -path "*/.*" -not -path "*/node_modules/*" -not -path "*/vendor/*" \
    -not -path "*/.venv/*" -not -path "*/venv/*" -print -quit | grep -q .
}

repo_has_tests() {
  find . -maxdepth 4 -type f \( -name "test_*.py" -o -name "*_test.py" \) \
    -not -path "*/.*" -not -path "*/node_modules/*" -not -path "*/.venv/*" \
    -not -path "*/vendor/*" -print -quit | grep -q .
}

has_script() {
  # El proyecto define este script en package.json. Se consulta antes de
  # correrlo: `--if-present` evita el error, pero pnpm igual imprime
  # "Missing script" y ese ruido se lee como un fallo que no ocurrio.
  [ -f package.json ] || return 1
  grep -q "\"$1\"[[:space:]]*:" package.json 2>/dev/null
}

STACK="mixed"
if [ -f pnpm-lock.yaml ]; then
  STACK="pnpm"
elif [ -f yarn.lock ]; then
  STACK="yarn"
elif [ -f bun.lockb ] || [ -f bun.lock ]; then
  STACK="bun"
elif [ -f package-lock.json ]; then
  STACK="npm"
elif [ -f uv.lock ] || [ -f pyproject.toml ]; then
  STACK="python"
elif [ -f requirements.txt ] || [ -f setup.py ]; then
  STACK="pip"
elif [ -f package.json ]; then
  STACK="npm"
elif has_python_files; then
  # Repo Python sin manifiesto: scripts sueltos, sin pyproject.toml ni
  # requirements.txt. Sin manifiesto no hay `uv run` posible, pero las
  # herramientas del PATH siguen sirviendo. Antes caia en `mixed` y no se
  # chequeaba nada: el gate verificaba el repo sin verificarlo.
  STACK="python"
elif [ -f go.mod ]; then
  STACK="go"
elif [ -f Cargo.toml ]; then
  STACK="cargo"
elif compgen -G "*.tf" > /dev/null 2>&1 || find . -maxdepth 3 -name "*.tf" -not -path "*/.*" -print -quit | grep -q .; then
  STACK="terraform"
elif [ -f Dockerfile ] || [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
  STACK="docker"
elif ! has_code_files && find . -maxdepth 3 -name "*.md" -not -path "*/.*" -not -path "*node_modules*" -print -quit | grep -q .; then
  STACK="docs"
fi

if [ "$DETECT_ONLY" -eq 1 ]; then
  echo "$STACK"
  exit 0
fi

echo "==> [pre-push-qa] Stack detected: $STACK"

STATUS=0

want_static() { [ "$SCOPE" != "tests" ]; }
want_tests() { [ "$SCOPE" != "static" ]; }

# ── Helpers de chequeo ────────────────────────────────────────────────────────────
# Todos acumulan su exit code en STATUS y nunca borran un fallo previo: el gate
# reporta el primer fallo, no el ultimo.

run_check() {
  # Etiqueta + comando. La salida completa se deja correr: el error tiene que
  # verse, no esconderse detras de un pipe.
  local label="$1"; shift
  echo "--> ${label}"
  "$@" || STATUS=$?
}

run_test_check() {
  # Igual que run_check, pero limita la salida a las ultimas 30 lineas. El
  # pipe conserva el exit code gracias a `set -o pipefail` (linea 3): sin eso,
  # un test fallido devuelve el codigo de `tail` y el gate lo aprueba.
  local label="$1"; shift
  echo "--> ${label}"
  "$@" 2>&1 | tail -30 || STATUS=$?
}

run_pytest() {
  # pytest sale con codigo 5 cuando no recolecta ningun test. Si el repo no
  # tiene archivos de test, eso no es un fallo del proyecto: es un proyecto sin
  # suite todavia, y el gate no debe bloquearlo. Si el repo SI tiene tests y
  # pytest no recolecta ninguno, el problema es real y se propaga.
  local label="$1"; shift
  local rc
  echo "--> ${label}"
  "$@" 2>&1 | tail -30
  rc=${PIPESTATUS[0]}
  if [ "$rc" -eq 5 ] && ! repo_has_tests; then
    echo "--> (no test files in repo — skipped)"
    rc=0
  fi
  return "$rc"
}

typecheck() {
  # TypeScript, solo si el proyecto lo declara.
  #
  # `--if-present` NO es un flag de tsc: pertenece al runner de scripts
  # (pnpm/npm/yarn run). tsc lo rechaza con "Unknown compiler option
  # '--if-present'" y sale con codigo 1, lo que hacia fallar el gate en TODOS
  # los repos TypeScript. La semantica que se quiere ("corre si el proyecto
  # tiene TypeScript") se decide aqui, mirando si hay tsconfig y si typescript
  # esta instalado.
  if [ ! -f tsconfig.json ]; then
    echo "--> Skipping typescript check (no tsconfig.json)."
    return 0
  fi
  local tsc_bin=""
  if [ -x "node_modules/.bin/tsc" ]; then
    tsc_bin="node_modules/.bin/tsc"
  elif command -v tsc >/dev/null 2>&1; then
    tsc_bin="tsc"
  else
    echo "--> Skipping typescript check (typescript is not installed)."
    return 0
  fi
  echo "--> Running typescript check (tsc --noEmit)..."
  "$tsc_bin" --noEmit || STATUS=$?
}

# Security check: Prevent pushing tracked .env files or private keys
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ENV_LEAKS="$(git ls-files 2>/dev/null | grep -E '(^|/)\.env(\.[^/]*)?$' | grep -vE '\.(example|sample|template|test|ci|defaults)$' || true)"
  if [ -n "$ENV_LEAKS" ]; then
    echo "==> [pre-push-qa] CRITICAL SECURITY ERROR: Sensitive .env files tracked in git:" >&2
    echo "$ENV_LEAKS" | sed 's/^/    /' >&2
    echo "    Untrack with: git rm --cached <file>" >&2
    STATUS=1
  fi

  KEY_LEAKS="$(git ls-files 2>/dev/null | grep -E '\.(pem|key|pkcs12|pfx|id_rsa|id_ed25519)$' || true)"
  if [ -n "$KEY_LEAKS" ]; then
    echo "==> [pre-push-qa] CRITICAL SECURITY ERROR: Private key files tracked in git:" >&2
    echo "$KEY_LEAKS" | sed 's/^/    /' >&2
    echo "    Untrack with: git rm --cached <file>" >&2
    STATUS=1
  fi

  # Working tree notice
  DIRTY_FILES="$(git status --porcelain 2>/dev/null || true)"
  if [ -n "$DIRTY_FILES" ]; then
    echo "==> [pre-push-qa] NOTICE: Working tree has uncommitted or unstaged changes:"
    echo "$DIRTY_FILES" | head -5 | sed 's/^/    /'
    echo "    Note: GitHub Actions CI will test only committed code in HEAD."
  fi
fi

case "$STACK" in
  python)
    # Dos casos distintos:
    #  - con manifiesto (pyproject.toml / uv.lock): el tooling es parte del
    #    contrato del proyecto. Si no esta disponible, el gate falla.
    #  - sin manifiesto: scripts sueltos. Las herramientas se usan si estan en
    #    el PATH; si no, el chequeo se marca como omitido. El gate no puede
    #    fallar por tooling que el repo nunca declaro.
    if [ -f uv.lock ] || [ -f pyproject.toml ]; then
      PY_MANIFEST=1
    else
      PY_MANIFEST=0
    fi

    if [ "$PY_MANIFEST" -eq 1 ] && command -v uv >/dev/null 2>&1; then
      PY_UV=1
    else
      PY_UV=0
    fi

    py_run() {
      if [ "$PY_UV" -eq 1 ]; then
        uv run "$@"
      else
        "$@"
      fi
    }

    py_has() {
      # Una herramienta que NO esta no es un fallo del proyecto: es un chequeo
      # que el proyecto nunca pidio. Se prueba antes de correrla.
      #
      # Con uv, `uv run <tool>` cae al PATH y, si tampoco esta ahi, responde
      # "Failed to spawn" con codigo 2. Eso se confundia con "el typecheck
      # fallo" y bloqueaba el push de un repo que no declara mypy: el mismo
      # repo pasaba en una maquina con mypy y fallaba en otra sin el.
      if [ "$PY_UV" -eq 1 ]; then
        uv run "$1" --version >/dev/null 2>&1
      else
        command -v "$1" >/dev/null 2>&1
      fi
    }

    if want_static; then
      if py_has ruff; then
        run_check "Running python lint (ruff)..." py_run ruff check . --output-format=concise
      else
        echo "--> Skipping python lint (ruff not available)."
      fi

      if py_has mypy; then
        run_check "Running python typecheck (mypy)..." py_run mypy . --ignore-missing-imports
      else
        echo "--> Skipping python typecheck (mypy not available)."
      fi
    fi

    if want_tests; then
      if py_has pytest; then
        run_pytest "Running python tests (pytest)..." py_run pytest -q --tb=line || STATUS=$?
      elif [ "$PY_MANIFEST" -eq 0 ] && command -v python3 >/dev/null 2>&1 && { [ -d tests ] || [ -d test ]; }; then
        run_test_check "Running python tests (unittest)..." python3 -m unittest discover -s .
      else
        echo "--> Skipping python tests (pytest not available)."
      fi
    fi

    # Sin herramientas disponibles no hay nada que verificar. Se reporta como
    # omitido, nunca como fallo: el gate no puede bloquear un push por tooling
    # que el proyecto no declaro.
    if want_static && [ "$PY_MANIFEST" -eq 1 ] && [ "$PY_UV" -eq 0 ]; then
      if ! command -v ruff >/dev/null 2>&1 && ! command -v mypy >/dev/null 2>&1 && ! command -v pytest >/dev/null 2>&1; then
        echo "--> Skipping python checks: no QA tools (ruff, mypy, pytest) found in PATH."
      fi
    fi
    ;;
  pip)
    echo "--> Running pip project checks..."
    local_found=0
    if want_static; then
      if command -v ruff >/dev/null 2>&1; then
        run_check "Running ruff check..." ruff check . --output-format=concise
        local_found=1
      fi
      if command -v mypy >/dev/null 2>&1; then
        run_check "Running mypy..." mypy . --ignore-missing-imports
        local_found=1
      fi
    fi
    if want_tests; then
      if command -v pytest >/dev/null 2>&1; then
        run_pytest "Running pytest..." pytest -q --tb=line || STATUS=$?
        local_found=1
      elif command -v python3 >/dev/null 2>&1 && { [ -d "tests" ] || [ -d "test" ]; }; then
        run_test_check "Running unittest..." python3 -m unittest discover -s .
        local_found=1
      fi
    fi
    if [ "$local_found" -eq 0 ]; then
      echo "--> Skipping python checks: no linter/test tools (ruff, mypy, pytest) found in PATH."
    fi
    ;;
  pnpm)
    if command -v pnpm >/dev/null 2>&1; then
      if want_static; then
        if has_script lint; then
          run_check "Running pnpm lint..." pnpm run lint
        fi
        typecheck
        if has_script build; then
          run_check "Running build check..." pnpm run build
        fi
      fi
      if want_tests && has_script test; then
        run_test_check "Running pnpm tests..." env CI=true pnpm test
      fi
    else
      echo "==> [pre-push-qa] ERROR: 'pnpm' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  npm)
    if command -v npm >/dev/null 2>&1; then
      if want_static; then
        if has_script lint; then
          run_check "Running npm lint..." npm run lint
        fi
        typecheck
        if has_script build; then
          run_check "Running build check..." npm run build
        fi
      fi
      if want_tests && has_script test; then
        run_test_check "Running npm tests..." env CI=true npm test
      fi
    else
      echo "==> [pre-push-qa] ERROR: 'npm' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  yarn)
    if command -v yarn >/dev/null 2>&1; then
      if want_static; then
        if has_script lint; then
          run_check "Running yarn lint..." yarn run lint
        fi
        typecheck
        if has_script build; then
          run_check "Running build check..." yarn run build
        fi
      fi
      if want_tests && has_script test; then
        run_test_check "Running yarn tests..." env CI=true yarn test
      fi
    else
      echo "==> [pre-push-qa] ERROR: 'yarn' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  bun)
    if command -v bun >/dev/null 2>&1; then
      if want_static; then
        if has_script lint; then
          run_check "Running bun lint..." bun run lint
        fi
        typecheck
        if has_script build; then
          run_check "Running build check..." bun run build
        fi
      fi
      if want_tests && has_script test; then
        run_test_check "Running bun tests..." env CI=true bun test
      fi
    else
      echo "==> [pre-push-qa] ERROR: 'bun' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  go)
    if command -v go >/dev/null 2>&1; then
      if want_static; then
        run_check "Running go vet..." go vet ./...
      fi
      if want_tests; then
        run_test_check "Running go tests..." go test ./...
      fi
    else
      echo "==> [pre-push-qa] ERROR: 'go' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  cargo)
    if command -v cargo >/dev/null 2>&1; then
      if want_static; then
        run_check "Running cargo check..." cargo check --all-targets
      fi
      if want_tests; then
        run_test_check "Running cargo tests..." cargo test
      fi
    else
      echo "==> [pre-push-qa] ERROR: 'cargo' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  terraform)
    if want_static && command -v terraform >/dev/null 2>&1; then
      run_check "Running terraform fmt check..." terraform fmt -check -recursive
    elif want_static; then
      echo "==> [pre-push-qa] ERROR: 'terraform' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  docker)
    if want_static && command -v hadolint >/dev/null 2>&1; then
      run_check "Running hadolint..." hadolint Dockerfile
    elif want_static; then
      echo "--> hadolint not found; skipping Dockerfile check."
    fi
    ;;
  docs)
    echo "--> Docs-only repository — static checks passed."
    ;;
  mixed|*)
    echo "--> Mixed or unknown stack — running best-effort checks..."
    if want_tests && has_script test && command -v npm >/dev/null 2>&1; then
      run_test_check "Running npm tests..." env CI=true npm test
    fi
    if want_static && command -v shellcheck >/dev/null 2>&1; then
      if find . -maxdepth 3 -name "*.sh" -not -path "*/.*" -print -quit | grep -q .; then
        run_check "Running shellcheck on shell scripts..." \
          find . -maxdepth 3 -name "*.sh" -not -path "*/.*" -exec shellcheck {} +
      fi
    fi
    ;;
esac

GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || echo "$REPO_ROOT/.git")"
CURRENT_HEAD="$(git rev-parse HEAD 2>/dev/null || echo "ok")"

# El marcador es para el push local: sirve para que el hook acepte el HEAD
# exacto. Un scope parcial (el que corre la CI) no aprueba ningun push, asi que
# no escribe marcador.
if [ "$SCOPE" != "all" ]; then
  if [ "$STATUS" -eq 0 ]; then
    echo "==> [pre-push-qa] Checks passed (scope: $SCOPE)."
    exit 0
  fi
  echo "==> [pre-push-qa] FAIL: Checks exited with status $STATUS (scope: $SCOPE)."
  exit 1
fi

if [ "$STATUS" -eq 0 ]; then
  if [ -d "$GIT_DIR" ]; then
    echo "$CURRENT_HEAD" > "$GIT_DIR/pre-push-qa-ok"
    rm -f "$REPO_ROOT/.pre-push-qa-ok" 2>/dev/null || true
  else
    echo "$CURRENT_HEAD" > "$REPO_ROOT/.pre-push-qa-ok" 2>/dev/null || true
  fi
  echo "==> [pre-push-qa] All checks passed successfully. Marker created for commit: ${CURRENT_HEAD:0:7}"
  exit 0
else
  if [ -d "$GIT_DIR" ]; then
    rm -f "$GIT_DIR/pre-push-qa-ok"
  fi
  rm -f "$REPO_ROOT/.pre-push-qa-ok"
  echo "==> [pre-push-qa] FAIL: Checks exited with status $STATUS. Refusing push."
  exit 1
fi
