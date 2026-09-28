#!/usr/bin/env bash
# examples/pre-push.sh
# Optional global git pre-push hook. Off by default.
# To activate: copy to ~/.githooks/pre-push and `git config --global core.hooksPath ~/.githooks`.
#
# This script BLOCKS any push that hasn't already passed the local pre-push-qa
# gate. Agents or scripts/run.sh write a marker containing the HEAD commit hash;
# this hook checks that marker, verifies it matches current HEAD, and consumes it.
#
# If you would rather ALWAYS run the gate directly (slower, but bulletproof),
# uncomment the hard mode branch below.

set -e

# Resolve the repo root and git dir
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
GIT_DIR="$(git rev-parse --git-dir 2>/dev/null || echo "$REPO_ROOT/.git")"
CURRENT_HEAD="$(git rev-parse HEAD 2>/dev/null || echo "")"

# Environment bypass switch
if [ "$SKIP_PRE_PUSH_QA" = "1" ]; then
  exit 0
fi

# Path-based detection: only enforce for known working repos (not third-party clones)
# Customize PRE_PUSH_QA_PATHS to match your environment if needed.
if [ -n "$PRE_PUSH_QA_PATHS" ]; then
  case "$REPO_ROOT" in
    $PRE_PUSH_QA_PATHS) ;;
    *) exit 0 ;;
  esac
else
  case "$REPO_ROOT" in
    /home/*/Proyectos/*|/home/*/Work/*|/home/*/Projects/*|/Users/*/Proyectos/*|/Users/*/Work/*|/Users/*/Projects/*) ;;
    *) exit 0 ;;
  esac
fi

# Safety check: Block push immediately if dangerous .env files or private keys are tracked
ENV_LEAKS="$(git ls-files 2>/dev/null | grep -E '(^|/)\.env(\.[^/]+)?$' | grep -vE '\.env\.(example|sample|template)$' || true)"
if [ -n "$ENV_LEAKS" ]; then
  echo "==> [pre-push-qa] CRITICAL PUSH BLOCKED: Tracked .env files detected:" >&2
  echo "$ENV_LEAKS" | sed 's/^/    /' >&2
  echo "    Untrack before pushing: git rm --cached <file>" >&2
  exit 1
fi

KEY_LEAKS="$(git ls-files 2>/dev/null | grep -E '\.(pem|key|pkcs12|pfx|id_rsa|id_ed25519)$' || true)"
if [ -n "$KEY_LEAKS" ]; then
  echo "==> [pre-push-qa] CRITICAL PUSH BLOCKED: Private key files tracked in git:" >&2
  echo "$KEY_LEAKS" | sed 's/^/    /' >&2
  echo "    Untrack before pushing: git rm --cached <file>" >&2
  exit 1
fi

# Notice if pushing with uncommitted working tree
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  echo "==> [pre-push-qa] NOTICE: Pushing while working tree has uncommitted changes." >&2
fi

# Hard mode (uncomment to run QA script on every push instead of checking marker):
# bash "$REPO_ROOT/scripts/run.sh" && exit 0

# Soft mode: verify and consume marker created by the agent or run.sh
MARKER=""
if [ -f "$GIT_DIR/pre-push-qa-ok" ]; then
  MARKER="$GIT_DIR/pre-push-qa-ok"
elif [ -f "$REPO_ROOT/.pre-push-qa-ok" ]; then
  MARKER="$REPO_ROOT/.pre-push-qa-ok"
fi

if [ -n "$MARKER" ]; then
  RECORDED_HASH="$(head -n 1 "$MARKER" 2>/dev/null | tr -d '[:space:]')"

  # Consume marker immediately on push so stale approvals cannot be reused
  rm -f "$GIT_DIR/pre-push-qa-ok" "$REPO_ROOT/.pre-push-qa-ok" 2>/dev/null || true

  # If marker records a specific commit hash, verify it matches current HEAD
  if [ -n "$RECORDED_HASH" ] && [ "$RECORDED_HASH" != "ok" ] && [ -n "$CURRENT_HEAD" ]; then
    if [ "$RECORDED_HASH" != "$CURRENT_HEAD" ]; then
      echo "==> [pre-push-qa] STALE MARKER ERROR: Marker was generated for commit ${RECORDED_HASH:0:7}, but HEAD is ${CURRENT_HEAD:0:7}." >&2
      echo "    You made new commits after running QA. Re-run QA checks before pushing." >&2
      exit 1
    fi
  fi

  echo "==> [pre-push-qa] Marker verified for commit ${CURRENT_HEAD:0:7}. Push allowed."
  exit 0
fi

echo "==> [pre-push-qa] BLOCKED: No valid QA verification marker found." >&2
echo "    Run your agent skill (pre-push-qa) or 'scripts/run.sh' before pushing." >&2
echo "    To bypass intentionally: git push --no-verify" >&2
exit 1
