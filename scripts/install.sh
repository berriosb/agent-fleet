#!/usr/bin/env bash
# scripts/install.sh — instala las skills de este repo en los directorios de agente.
#
# Por que existe
# ──────────────
# `npx skills add berriosb/agent-fleet -g` deja las skills SOLO en
# ~/.agents/skills/. De ahi leen OpenCode, Amp, Antigravity, Cline y otros
# veinte. Pero Claude Code lee ~/.claude/skills, Codex lee ~/.codex/skills y
# Gemini lee ~/.gemini/skills: ninguno de esos tres recibe nada.
#
# Peor: el resultado no es lo que `check-install.py` exige. El repo se
# declara roto despues de una instalacion "correcta" por el comando que el
# propio README pone primero. Este script deja la maquina en el estado que el
# repo exige.
#
# Que hace
# ───────
# 1. Enlaza el DIRECTORIO completo de cada skill (no solo SKILL.md: sin
#    scripts/ y prompts/ el agente no puede correr el runner) en los cuatro
#    roots.
# 2. Resuelve las copias divergentes de las skills del repo en los perfiles de
#    Hermes: las reemplaza por enlaces al repo.
# 3. Enlaza el runner en ~/.local/bin.
# 4. Con --hook, instala tambien el hook global de push (enforcement duro).
# 5. Corre check-install.py al final, para que el resultado no sea una promesa.
#
# Lo que NO toca: las skills de otros origenes (omarchy, find-skills, mmx-cli).
# El loop solo recorre las skills de este repo.
#
# Nada se borra con rm: lo que se reemplaza va a la papelera con `gio trash`, y
# se puede recuperar desde ~/.local/share/Trash.
#
# Uso
# ───
#   ./scripts/install.sh            # skills + runner
#   ./scripts/install.sh --hook     # ademas, el hook global de push
set -eo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

SRC="$REPO_ROOT/skills"
ROOTS=(
  "$HOME/.agents/skills"
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.gemini/skills"
)
WITH_HOOK=0

for arg in "$@"; do
  case "$arg" in
    --hook) WITH_HOOK=1 ;;
    -h|--help)
      echo "usage: install.sh [--hook]"
      echo "  (sin flags)  enlaza las skills y el runner."
      echo "  --hook       instala tambien el hook global de push."
      exit 0
      ;;
    *)
      echo "==> [install] ERROR: argumento desconocido '$arg' (usar --hook)" >&2
      exit 2
      ;;
  esac
done

if [ ! -d "$SRC" ]; then
  echo "==> [install] ERROR: no se encuentra $SRC" >&2
  exit 1
fi

trash_or_skip() {
  # Manda a la papelera. Si no se puede, lo dice y no borra con rm: la linea
  # roja del repo prohibe borrar datos de otra forma.
  local target="$1"
  if ! command -v gio >/dev/null 2>&1; then
    echo "    (gio no esta: no se puede manda '$target' a la papelera, se deja como está)" >&2
    return 1
  fi
  if ! gio trash "$target" 2>/dev/null; then
    echo "    (no se pudo mandar '$target' a la papelera, se deja como está)" >&2
    return 1
  fi
  return 0
}

link_skill() {
  # Deja $2 como enlace al directorio de la skill $1. Reemplaza lo que haya.
  local source_dir="$1" dest="$2"
  local name
  name="$(basename "$source_dir")"

  if [ -L "$dest" ]; then
    local current
    current="$(readlink "$dest")"
    if [ "${current%/}" = "${source_dir%/}" ]; then
      echo "    = $dest"
      return 0
    fi
    if trash_or_skip "$dest"; then
      ln -sfn "$source_dir" "$dest"
      echo "    ~ $dest (reapuntado: antes apuntaba a $current)"
    else
      echo "    ! $dest (no se pudo reemplazar)" >&2
    fi
    return 0
  fi

  if [ -e "$dest" ]; then
    if trash_or_skip "$dest"; then
      ln -sfn "$source_dir" "$dest"
      echo "    ~ $dest (copia reemplazada por enlace)"
    else
      echo "    ! $dest (copia sin reemplazar)" >&2
    fi
    return 0
  fi

  ln -sfn "$source_dir" "$dest"
  echo "    + $dest"
}

echo "==> [install] 1/4 Enlazando las skills en los directorios de agente..."
for dest in "${ROOTS[@]}"; do
  mkdir -p "$dest"
  echo "  $dest"
  for skill in "$SRC"/*/; do
    link_skill "$skill" "$dest/$(basename "$skill")"
  done
done

echo "==> [install] 2/4 Resolviendo copias divergentes en los perfiles de Hermes..."
HERMES_FOUND=0
if [ -d "$HOME/.hermes/profiles" ]; then
  for profile in "$HOME/.hermes/profiles"/*/; do
    [ -d "${profile}skills" ] || continue
    for category in "${profile}skills"/*/; do
      [ -d "$category" ] || continue
      for skill in "$SRC"/*/; do
        candidate="$category$(basename "$skill")"
        [ -e "$candidate" ] || [ -L "$candidate" ] || continue
        HERMES_FOUND=1
        echo "  ${profile%/}:"
        link_skill "$skill" "$candidate"
      done
    done
  done
fi
[ "$HERMES_FOUND" -eq 1 ] || echo "  (ningun perfil de Hermes con copias de estas skills)"

echo "==> [install] 3/4 Enlazando el runner en ~/.local/bin..."
mkdir -p "$HOME/.local/bin"
link_skill "$SRC/pre-push-qa/scripts/run.sh" "$HOME/.local/bin/pre-push-qa"

if [ "$WITH_HOOK" -eq 1 ]; then
  echo "==> [install] 3b/4 Instalando el hook global de push..."
  mkdir -p "$HOME/.githooks"
  cp "$SRC/pre-push-qa/examples/pre-push.sh" "$HOME/.githooks/pre-push"
  chmod +x "$HOME/.githooks/pre-push"
  git config --global core.hooksPath "$HOME/.githooks"
  echo "    ~ $HOME/.githooks/pre-push (core.hooksPath = $HOME/.githooks)"
else
  echo "==> [install] 3b/4 Hook global: omitido (con --hook se instala)"
fi

echo "==> [install] 4/4 Verificando..."
python3 scripts/check-install.py
