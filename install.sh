#!/usr/bin/env bash
#
# BuildCLI Agents installer — run this from inside the project you want to set up.
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/wheslleyrimar/buildcli-agents/main/install.sh)
#   bash <(curl -fsSL .../install.sh) --agent claude
#   bash <(curl -fsSL .../install.sh) --agent all --mode link

set -euo pipefail

REPO_URL="${BUILDCLI_REPO_URL:-https://github.com/wheslleyrimar/buildcli-agents.git}"
TMP_DIR="$(mktemp -d)"
TARGET="$(pwd)"
AGENT="all"
MODE="copy"

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
    -h|--help)
      echo "Usage: install.sh [--agent claude|codex|gemini|copilot|all] [--mode copy|link] [--target PATH]"
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

echo ""
echo "  BuildCLI Agents installer"
echo "  ───────────────"
echo "  target : $TARGET"
echo "  agent  : $AGENT"
echo "  mode   : $MODE"
echo ""

if [[ "$MODE" == "link" ]]; then
  # Symlinks must point at a tree that survives this script, so keep a real clone.
  if [[ -d "$LINK_SRC/.git" ]]; then
    echo "Updating BuildCLI Agents source at $LINK_SRC..."
    git -C "$LINK_SRC" pull --quiet --ff-only
  else
    echo "Cloning BuildCLI Agents source to $LINK_SRC (shared by every linked project)..."
    git clone --quiet "$REPO_URL" "$LINK_SRC"
  fi
  SOURCE_ROOT="$LINK_SRC"
else
  echo "Fetching BuildCLI Agents..."
  git clone --quiet --depth 1 "$REPO_URL" "$TMP_DIR"
  SOURCE_ROOT="$TMP_DIR"
fi

bash "$SOURCE_ROOT/buildcli/scripts/bootstrap.sh" \
  --repo "$TARGET" \
  --agent "$AGENT" \
  --mode "$MODE"

cat <<'NEXT'

Next steps:
  1. Open the project in your agent.
  2. survey            → profile the repo into .buildcli/context.md, split into bands
  3. brief <describe>  → requirements with acceptance criteria; sets .buildcli/active
  4. shape             → architecture and a phased plan
  5. worklist          → atomic units with dependencies and band tags
  6. build             → execute the worklist band by band
  7. audit             → check the implementation against the brief

  Any time:  pulse (where am I) · focus (switch blueprint) · patch (fix a defect)
  Claude Code only:  rig  → hooks, permissions, and the audit journal

NEXT
