#!/usr/bin/env bash
#
# BuildCLI Agents installer — run this from inside the project you want to set up.
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/wheslleyrimar/BuildCLI-Agents/main/install.sh)
#   bash <(curl -fsSL .../install.sh) --agent claude
#   bash <(curl -fsSL .../install.sh) --agent all --mode link
#   bash <(curl -fsSL .../install.sh) --shim          # also put `bcx` on PATH

set -euo pipefail

REPO_URL="${BUILDCLI_REPO_URL:-https://github.com/wheslleyrimar/BuildCLI-Agents.git}"
TMP_DIR="$(mktemp -d)"
TARGET="$(pwd)"
AGENT="all"
MODE="copy"

# The shim is the one artifact that lands outside the target directory, so it is
# never silently installed: asked for interactively, or requested by flag.
SHIM="ask"
SHIM_DIR=""
VERBOSE=0

# link mode needs a source tree that outlives this script, so it is cloned here
# instead of into a temp directory. Pull it to update every linked project at once.
LINK_SRC="${BUILDCLI_HOME:-$HOME/.buildcli}"

cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)  AGENT="$2";  shift 2 ;;
    --mode)   MODE="$2";   shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --shim)      SHIM="yes"; shift ;;
    --no-shim)   SHIM="no";  shift ;;
    --shim-dir)  SHIM="yes"; SHIM_DIR="$2"; shift 2 ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help)
      cat <<'USAGE'
Usage: install.sh [--agent claude|codex|gemini|copilot|all] [--mode copy|link] [--target PATH]
                  [--shim | --no-shim] [--shim-dir PATH] [--verbose]

  --shim      install the `bcx` PATH dispatcher without asking (default dir: ~/bin)
  --no-shim   skip it without asking
  --shim-dir  install it to a specific directory
  --verbose   list every file installed instead of a summary line per agent

  With neither flag, the installer asks — and skips the question when there is no
  terminal to ask on (piped input, CI).
USAGE
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

case "$AGENT" in
  claude|codex|gemini|copilot|all) ;;
  *) echo "Invalid --agent: $AGENT  (claude | codex | gemini | copilot | all)" >&2; exit 1 ;;
esac

case "$MODE" in
  copy|link) ;;
  *) echo "Invalid --mode: $MODE  (copy | link)" >&2; exit 1 ;;
esac

if [[ ! -d "$TARGET" ]]; then
  echo "Target directory does not exist: $TARGET" >&2
  exit 1
fi

# ── output ────────────────────────────────────────────────────────────────────
# Color only on a real terminal, so piped output and CI logs stay plain.

if [[ -t 1 && -z "${NO_COLOR:-}" && "${TERM:-dumb}" != "dumb" ]]; then
  C_RESET=$'\033[0m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'
  C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'
  MARK_OK="✔"; MARK_WARN="!"
else
  C_RESET=""; C_DIM=""; C_BOLD=""; C_GREEN=""; C_YELLOW=""
  MARK_OK="OK"; MARK_WARN="!"
fi

step() { printf '  %s%s%s %s\n' "$C_GREEN" "$MARK_OK" "$C_RESET" "$1"; }
warn() { printf '  %s%s%s %s\n' "$C_YELLOW" "$MARK_WARN" "$C_RESET" "$1" >&2; }

# ── prerequisites ─────────────────────────────────────────────────────────────
# The markdown pipeline works without python3; the runtime and its enforcement
# gates do not. Warn loudly rather than failing later, mid-session.
PYTHON_OK=1
if ! command -v python3 >/dev/null 2>&1; then
  PYTHON_OK=0
fi

printf '\n  %sBuildCLI Agents%s %sinstaller%s\n' "$C_BOLD" "$C_RESET" "$C_DIM" "$C_RESET"
printf '  %s%s%s\n' "$C_DIM" "$TARGET" "$C_RESET"
if [[ "$PYTHON_OK" -eq 1 ]]; then
  printf '  %sagent %s · mode %s · %s%s\n\n' \
    "$C_DIM" "$AGENT" "$MODE" "$(python3 --version 2>&1)" "$C_RESET"
else
  printf '  %sagent %s · mode %s · python3 NOT FOUND%s\n\n' \
    "$C_DIM" "$AGENT" "$MODE" "$C_RESET"
fi

if [[ "$PYTHON_OK" -eq 0 ]]; then
  cat >&2 <<'WARN'
  WARNING: python3 is not on PATH.

  The commands and skills install fine and the pipeline still works, but the
  runtime (.buildcli/runtime/bcx) cannot run. That means no deterministic band
  extraction, no dependency scheduling, no executable verification, and no
  enforcement gates from `rig --enforce`.

  Install python3 (3.8 or newer) and re-run this installer to get them.

WARN
fi

if [[ "$MODE" == "link" ]]; then
  # Symlinks must point at a tree that survives this script, so keep a real clone.
  if [[ -d "$LINK_SRC/.git" ]]; then
    git -C "$LINK_SRC" pull --quiet --ff-only
    step "Updated the shared source at $LINK_SRC"
  else
    git clone --quiet "$REPO_URL" "$LINK_SRC"
    step "Cloned the shared source to $LINK_SRC"
  fi
  SOURCE_ROOT="$LINK_SRC"
else
  git clone --quiet --depth 1 "$REPO_URL" "$TMP_DIR"
  step "Fetched BuildCLI Agents"
  SOURCE_ROOT="$TMP_DIR"
fi

# The banner above already said target, agent and mode.
BOOTSTRAP_ARGS=(--repo "$TARGET" --agent "$AGENT" --mode "$MODE" --no-banner)
[[ "$VERBOSE" == "1" ]] && BOOTSTRAP_ARGS+=(--verbose)

bash "$SOURCE_ROOT/buildcli/scripts/bootstrap.sh" "${BOOTSTRAP_ARGS[@]}"

# ── the PATH shim ─────────────────────────────────────────────────────────────
# Everything above stayed inside $TARGET. This step writes to the user's home,
# so it needs an explicit yes: a flag, or an answer at a terminal.

RUNTIME="$TARGET/.buildcli/runtime/bcx"
SHIM_INSTALLED=0

shim_rc_hint() {
  # The runtime warns that the directory is off PATH; this prints the exact fix.
  local dir="$1" rc
  case "$(basename "${SHELL:-}")" in
    zsh)  rc="~/.zshrc"      ;;
    bash) rc="~/.bash_profile" ;;
    fish) rc="~/.config/fish/config.fish" ;;
    *)    rc="your shell's startup file" ;;
  esac
  echo ""
  echo "  To finish, add it to your PATH in $rc:"
  if [[ "$(basename "${SHELL:-}")" == "fish" ]]; then
    echo "      fish_add_path $dir"
  else
    echo "      export PATH=\"$dir:\$PATH\""
  fi
  echo "  Then open a new terminal, or re-source that file."
}

install_shim() {
  local dir="${SHIM_DIR:-$HOME/bin}"
  echo ""
  local args=(shim --install)
  [[ -n "$SHIM_DIR" ]] && args+=(--dir "$SHIM_DIR")
  # The runtime prints its own three lines; keep only what the user must act on.
  local out
  if ! out="$("$RUNTIME" "${args[@]}" 2>&1)"; then
    warn "bcx dispatcher not installed — the full path still works:"
    echo "      $RUNTIME <command>" >&2
    echo "$out" | sed 's/^/      /' >&2
    return 1
  fi
  step "Dispatcher  $C_DIM$dir/bcx$C_RESET"
  while IFS= read -r line; do
    # The off-PATH note is answered by shim_rc_hint below; don't say it twice.
    [[ "$line" == *"note "* && "$line" != *"not on your PATH"* ]] && \
      warn "${line#*note       }"
  done <<< "$out"
  SHIM_INSTALLED=1
  case ":${PATH}:" in
    *":$dir:"*) ;;
    *) shim_rc_hint "$dir" ;;
  esac
}

if [[ "$SHIM" != "no" && "$PYTHON_OK" -eq 0 ]]; then
  # Without python3 the dispatcher would resolve to a runtime that cannot run.
  [[ "$SHIM" == "yes" ]] && echo "" && \
    echo "Skipping the bcx dispatcher: it needs python3, which is not on PATH."
  SHIM="no"
fi

if [[ "$SHIM" == "ask" ]]; then
  if [[ -t 0 ]]; then
    printf '\n  %sThe runtime already works as .buildcli/runtime/bcx.%s\n' \
      "$C_DIM" "$C_RESET"
    printf '  %sA dispatcher in %s lets you type plain `bcx` from any project —\n' \
      "$C_DIM" "${SHIM_DIR:-~/bin}"
    printf '  the only file written outside %s.%s\n' "$TARGET" "$C_RESET"
    printf '  Install it? [y/N] '
    read -r reply || reply=""
    case "$reply" in
      [yY]|[yY][eE][sS]) SHIM="yes" ;;
      *) SHIM="no" ;;
    esac
  else
    SHIM="no"   # no terminal to ask on; --shim is the way to request it
  fi
fi

if [[ "$SHIM" == "yes" ]]; then
  install_shim || true
fi

# ── what to do next ───────────────────────────────────────────────────────────
# The pipeline order, one line each. Anything longer stops being read.

printf '\n  %sNext, in your agent%s\n' "$C_BOLD" "$C_RESET"
stage() { printf '    %s%s%s  %s%s%s\n' "$C_BOLD" "$1" "$C_RESET" "$C_DIM" "$2" "$C_RESET"; }
stage "survey          " "profile the repo into .buildcli/context.md"
stage "brief <describe>" "requirements + acceptance criteria; sets active"
stage "shape           " "architecture and a phased plan"
stage "worklist        " "atomic units, dependencies, band tags"
stage "build           " "execute the worklist band by band"
stage "audit           " "check the build against the brief"
printf '    %sany time: pulse · focus · patch   ·   hooks: rig --enforce%s\n' \
  "$C_DIM" "$C_RESET"

printf '\n  %sAnd in your terminal%s\n' "$C_BOLD" "$C_RESET"
if [[ "$SHIM_INSTALLED" -eq 1 ]]; then
  printf '    bcx doctor %s— from anywhere in the project%s\n' "$C_DIM" "$C_RESET"
else
  printf '    .buildcli/runtime/bcx doctor %s— from the project root%s\n' "$C_DIM" "$C_RESET"
  printf '    %sshort form: .buildcli/runtime/bcx shim --install%s\n' "$C_DIM" "$C_RESET"
fi
echo ""
