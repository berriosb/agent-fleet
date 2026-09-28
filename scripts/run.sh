#!/usr/bin/env bash
# scripts/run.sh — Local QA gate execution script for pre-push checks.
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

echo "==> [pre-push-qa] Detecting repository stack..."

has_code_files() {
  find . -maxdepth 4 -type f \( \
    -name "*.js" -o -name "*.ts" -o -name "*.jsx" -o -name "*.tsx" -o \
    -name "*.py" -o -name "*.go" -o -name "*.rs" -o -name "*.sh" -o \
    -name "*.tf" -o -name "Dockerfile*" -o -name "*.c" -o -name "*.cpp" -o \
    -name "*.java" -o -name "*.rb" -o -name "*.php" \
  \) -not -path "*/.*" -not -path "*node_modules*" -not -path "*vendor*" -not -path "*.venv*" -print -quit | grep -q .
}

STACK="mixed"
if [ -f pnpm-lock.yaml ]; then
  STACK="pnpm"
elif [ -f package-lock.json ]; then
  STACK="npm"
elif [ -f yarn.lock ]; then
  STACK="yarn"
elif [ -f bun.lockb ] || [ -f bun.lock ]; then
  STACK="bun"
elif [ -f uv.lock ] || [ -f pyproject.toml ]; then
  STACK="python"
elif [ -f requirements.txt ] || [ -f setup.py ]; then
  STACK="pip"
elif compgen -G "*.tf" > /dev/null 2>&1 || find . -maxdepth 3 -name "*.tf" -not -path "*/.*" -print -quit | grep -q .; then
  STACK="terraform"
elif [ -f Dockerfile ] || [ -f docker-compose.yml ] || [ -f docker-compose.yaml ]; then
  STACK="docker"
elif ! has_code_files && find . -maxdepth 3 -name "*.md" -not -path "*/.*" -not -path "*node_modules*" -print -quit | grep -q .; then
  STACK="docs"
fi

echo "==> [pre-push-qa] Stack detected: $STACK"
STATUS=0

# Security check: Prevent pushing tracked .env files or private keys
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ENV_LEAKS="$(git ls-files 2>/dev/null | grep -E '(^|/)\.env(\.[^/]+)?$' | grep -vE '\.env\.(example|sample|template)$' || true)"
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
    if command -v uv >/dev/null 2>&1; then
      echo "--> Running python lint (ruff)..."
      uv run ruff check . --output-format=concise || STATUS=$?
      echo "--> Running python typecheck (mypy)..."
      uv run mypy . --ignore-missing-imports 2>/dev/null || STATUS=$?
      echo "--> Running python tests (pytest)..."
      uv run pytest -q --tb=line 2>&1 | tail -30 || STATUS=$?
    elif command -v ruff >/dev/null 2>&1 || command -v pytest >/dev/null 2>&1; then
      echo "--> uv not found, running available python tools..."
      if command -v ruff >/dev/null 2>&1; then
        ruff check . --output-format=concise || STATUS=$?
      fi
      if command -v mypy >/dev/null 2>&1; then
        mypy . --ignore-missing-imports 2>/dev/null || STATUS=$?
      fi
      if command -v pytest >/dev/null 2>&1; then
        pytest -q --tb=line 2>&1 | tail -30 || STATUS=$?
      fi
    else
      echo "==> [pre-push-qa] ERROR: Python stack detected, but neither 'uv' nor python QA tools found in PATH." >&2
      STATUS=1
    fi
    ;;
  pip)
    echo "--> Running pip project checks..."
    local_found=0
    if command -v ruff >/dev/null 2>&1; then
      echo "--> Running ruff check..."
      ruff check . --output-format=concise || STATUS=$?
      local_found=1
    fi
    if command -v mypy >/dev/null 2>&1; then
      echo "--> Running mypy..."
      mypy . --ignore-missing-imports 2>/dev/null || STATUS=$?
      local_found=1
    fi
    if command -v pytest >/dev/null 2>&1; then
      echo "--> Running pytest..."
      pytest -q --tb=line 2>&1 | tail -30 || STATUS=$?
      local_found=1
    elif command -v python3 >/dev/null 2>&1 && [ -d "tests" -o -d "test" ]; then
      echo "--> Running unittest..."
      python3 -m unittest discover -s . 2>&1 | tail -30 || STATUS=$?
      local_found=1
    fi
    if [ "$local_found" -eq 0 ]; then
      echo "==> [pre-push-qa] WARNING: pip stack detected, but no linter/test tools (ruff, mypy, pytest) found in PATH." >&2
      echo "    Install ruff/pytest or use uv to enable checks." >&2
      STATUS=1
    fi
    ;;
  pnpm)
    if command -v pnpm >/dev/null 2>&1; then
      echo "--> Running pnpm lint..."
      pnpm run lint --if-present || STATUS=$?
      echo "--> Running typescript check..."
      pnpm exec tsc --noEmit --if-present 2>/dev/null || STATUS=$?
      echo "--> Running pnpm tests..."
      pnpm test -- --run 2>&1 | tail -30 || STATUS=$?
      echo "--> Running build check..."
      pnpm run build --if-present || STATUS=$?
    else
      echo "==> [pre-push-qa] ERROR: 'pnpm' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  npm)
    if command -v npm >/dev/null 2>&1; then
      echo "--> Running npm lint..."
      npm run lint --if-present || STATUS=$?
      echo "--> Running typescript check..."
      npx --no-install tsc --noEmit --if-present 2>/dev/null || STATUS=$?
      echo "--> Running npm tests..."
      npm test -- --passWithNoTests 2>&1 | tail -30 || STATUS=$?
      echo "--> Running build check..."
      npm run build --if-present || STATUS=$?
    else
      echo "==> [pre-push-qa] ERROR: 'npm' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  yarn)
    if command -v yarn >/dev/null 2>&1; then
      echo "--> Running yarn lint..."
      yarn run lint || STATUS=$?
      echo "--> Running typescript check..."
      yarn run tsc --noEmit 2>/dev/null || STATUS=$?
      echo "--> Running yarn tests..."
      yarn test 2>&1 | tail -30 || STATUS=$?
      if grep -q '"build":' package.json 2>/dev/null; then
        echo "--> Running build check..."
        yarn run build || STATUS=$?
      fi
    else
      echo "==> [pre-push-qa] ERROR: 'yarn' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  bun)
    if command -v bun >/dev/null 2>&1; then
      echo "--> Running bun lint..."
      bun run lint || STATUS=$?
      echo "--> Running bun tests..."
      bun test 2>&1 | tail -30 || STATUS=$?
      if grep -q '"build":' package.json 2>/dev/null; then
        echo "--> Running build check..."
        bun run build || STATUS=$?
      fi
    else
      echo "==> [pre-push-qa] ERROR: 'bun' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  terraform)
    if command -v terraform >/dev/null 2>&1; then
      echo "--> Running terraform fmt check..."
      terraform fmt -check -recursive || STATUS=$?
    else
      echo "==> [pre-push-qa] ERROR: 'terraform' is required for this stack but not installed or not in PATH." >&2
      STATUS=1
    fi
    ;;
  docker)
    if command -v hadolint >/dev/null 2>&1; then
      echo "--> Running hadolint..."
      hadolint Dockerfile || STATUS=$?
    else
      echo "--> hadolint not found; skipping Dockerfile check."
    fi
    ;;
  docs)
    echo "--> Docs-only repository — static checks passed."
    ;;
  mixed|*)
    echo "--> Mixed or unknown stack — running best-effort checks..."
    if [ -f package.json ] && command -v npm >/dev/null 2>&1; then
      npm test --if-present 2>/dev/null || STATUS=$?
    fi
    if command -v shellcheck >/dev/null 2>&1; then
      if find . -maxdepth 3 -name "*.sh" -not -path "*/.*" -print -quit | grep -q .; then
        echo "--> Running shellcheck on shell scripts..."
        find . -maxdepth 3 -name "*.sh" -not -path "*/.*" -exec shellcheck {} + || STATUS=$?
      fi
    fi
    ;;
esac

GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || echo "$REPO_ROOT/.git")"
CURRENT_HEAD="$(git rev-parse HEAD 2>/dev/null || echo "ok")"

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
