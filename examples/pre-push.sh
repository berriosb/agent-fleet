#!/usr/bin/env bash
# examples/pre-push.sh
# Optional global git pre-push hook. Off by default.
# To activate: copy to ~/.githooks/pre-push and `git config --global core.hooksPath ~/.githooks`.
#
# This script BLOCKS any push that hasn't already passed the local pre-push-qa
# skill. Agents write a marker file when the skill passes; this hook checks
# for that marker and refuses to push without it.
#
# If you would rather ALWAYS run the gate (slower, but bulletproof), uncomment
# the alternative branch below.

set -e

# Resolve the repo root from the git working tree
REPO_ROOT="$(git rev-parse --show-toplevel)"

# Path-based detection: only enforce for known working repos (not third-party clones)
case "$REPO_ROOT" in
  /home/*/Proyectos/*|/home/*/Work/*) ;;
  *) exit 0 ;;
esac

# Soft mode: trust the agent that loaded pre-push-qa
if [ -f "$REPO_ROOT/.pre-push-qa-ok" ]; then
  exit 0
fi

# Hard mode (uncomment to use instead of soft mode):
# bash "$HOME/.hermes/profiles/codehak/skills/software-development/pre-push-qa/scripts/run.sh"

echo "pre-push-qa: no .pre-push-qa-ok marker found."
echo "Run the agent skill first (the agent will create the marker on success),"
echo "or use 'git push --no-verify' to bypass this hook (NOT RECOMMENDED)."
exit 1
