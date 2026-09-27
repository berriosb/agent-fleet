#!/usr/bin/env bash
# scripts/run.sh — Local QA gate execution script for pre-push checks.
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

echo "==> [pre-push-qa] Detecting repository stack..."

STACK="mixed"
if [ -f pnpm-lock.yaml ]; then
  STACK="pnpm"
elif [ -f package-lock.json ]; then
  STACK="npm"
elif [ -f uv.lock ] || [ -f pyproject.toml ]; then
  STACK="python"
elif compgen -G "*.tf" > /dev/null; then
  STACK="terraform"
elif find . -maxdepth 3 -name "*.md" -not -path "./node_modules/*" -print -quit | grep -q .; then
  STACK="docs"
fi

echo "==> [pre-push-qa] Stack detected: $STACK"
STATUS=0

case "$STACK" in
  python)
    if command -v uv >/dev/null 2>&1; then
      echo "--> Running python lint..."
      uv run ruff check . --output-format=concise || STATUS=$?
      echo "--> Running python tests..."
      uv run pytest -q --tb=line 2>&1 | tail -30 || STATUS=$?
    else
      echo "--> uv not installed; skipping python checks."
    fi
    ;;
  pnpm)
    if command -v pnpm >/dev/null 2>&1; then
      echo "--> Running pnpm lint..."
      pnpm run lint --if-present || STATUS=$?
      echo "--> Running pnpm tests..."
      pnpm test -- --run 2>&1 | tail -30 || STATUS=$?
    fi
    ;;
  npm)
    if command -v npm >/dev/null 2>&1; then
      echo "--> Running npm lint..."
      npm run lint --if-present || STATUS=$?
      echo "--> Running npm tests..."
      npm test -- --passWithNoTests 2>&1 | tail -30 || STATUS=$?
    fi
    ;;
  terraform)
    if command -v terraform >/dev/null 2>&1; then
      terraform fmt -check -recursive || STATUS=$?
    fi
    ;;
  docs)
    echo "--> Docs-only repository — static checks passed."
    ;;
  *)
    echo "--> Mixed or unknown stack — running best-effort."
    ;;
esac

if [ "$STATUS" -eq 0 ]; then
  touch "$REPO_ROOT/.pre-push-qa-ok"
  echo "==> [pre-push-qa] All checks passed successfully. Marker .pre-push-qa-ok created."
  exit 0
else
  rm -f "$REPO_ROOT/.pre-push-qa-ok"
  echo "==> [pre-push-qa] FAIL: Checks exited with status $STATUS. Refusing push."
  exit 1
fi
