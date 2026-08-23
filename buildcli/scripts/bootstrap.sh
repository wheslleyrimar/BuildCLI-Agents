#!/usr/bin/env bash
#
# BuildCLI Agents bootstrap — installs commands and skills into a target project's
# native agent folders, and writes the autoload block into each agent's
# startup file.

set -euo pipefail

usage() {
  cat <<'HELP'
Usage:
  ./buildcli/scripts/bootstrap.sh [--repo PATH] [--agent AGENT] [--mode copy|link]

Options:
  --repo PATH     Target repository. Default: current directory.
  --agent AGENT   claude | codex | gemini | copilot | all. Default: all.
  --mode MODE     copy | link. Default: copy.
  -h, --help      Show this help.

Examples:
  ./buildcli/scripts/bootstrap.sh
  ./buildcli/scripts/bootstrap.sh --repo /path/to/project --agent claude
  ./buildcli/scripts/bootstrap.sh --repo /path/to/project --agent all --mode link
HELP
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_PATH="$(pwd)"
AGENT="all"
MODE="copy"
BEGIN_MARK="<!-- buildcli:autoload:start -->"
CLOSE_MARK="<!-- buildcli:autoload:end -->"

BANDS=(service interface store verify delivery)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)  REPO_PATH="$2"; shift 2 ;;
    --agent) AGENT="$2";     shift 2 ;;
    --mode)  MODE="$2";      shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ ! -d "$REPO_PATH" ]]; then
  echo "Target repo does not exist: $REPO_PATH" >&2
  exit 1
fi
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

# Guard against the common mistake of pointing --repo at the kit itself.
if [[ "$REPO_PATH" == "$KIT_ROOT" || "$REPO_PATH" == "$KIT_ROOT"/* ]]; then
  echo "ERROR: --repo points inside the buildcli/ kit ($REPO_PATH)." >&2
  echo "  Run from your project root, or pass --repo /path/to/your/project" >&2
  exit 1
fi

case "$AGENT" in
  claude|codex|gemini|copilot|all) ;;
  *) echo "Invalid --agent: $AGENT  (claude | codex | gemini | copilot | all)" >&2; exit 1 ;;
esac

case "$MODE" in
  copy|link) ;;
  *) echo "Invalid --mode: $MODE  (copy | link)" >&2; exit 1 ;;
esac

# ── file installation ─────────────────────────────────────────────────────────

install_commands() {
  local src_dir="$1" dest_dir="$2" file base dest
  [[ -d "$src_dir" ]] || return 0
  mkdir -p "$dest_dir"
  for file in "$src_dir"/*.md; do
    [[ -f "$file" ]] || continue
    base="$(basename "$file")"
    dest="$dest_dir/$base"
    if [[ "$MODE" == "copy" ]]; then cp "$file" "$dest"; else ln -sfn "$file" "$dest"; fi
    echo "  command  $dest"
  done
}

install_skills() {
  local src_dir="$1" dest_dir="$2" skill_dir name dest src_file
  [[ -d "$src_dir" ]] || return 0
  for skill_dir in "$src_dir"/*/; do
    [[ -d "$skill_dir" ]] || continue
    name="$(basename "$skill_dir")"
    src_file="$skill_dir/SKILL.md"
    [[ -f "$src_file" ]] || continue
    dest="$dest_dir/$name"
    mkdir -p "$dest"
    if [[ "$MODE" == "copy" ]]; then cp "$src_file" "$dest/SKILL.md"; else ln -sfn "$src_file" "$dest/SKILL.md"; fi
    echo "  skill    $dest/SKILL.md"
  done
}

# ── shared state ──────────────────────────────────────────────────────────────

ensure_state() {
  local context="$REPO_PATH/.buildcli/context.md"
  local template="$KIT_ROOT/_shared/templates/context-template.md"

  mkdir -p "$REPO_PATH/.buildcli"
  mkdir -p "$REPO_PATH/blueprints/features"
  mkdir -p "$REPO_PATH/blueprints/defects"

  if [[ ! -f "$context" ]]; then
    if [[ -f "$template" ]]; then
      cp "$template" "$context"
      echo "  state    $context"
    else
      printf '# Project Context\n\nTODO: run the `survey` skill to populate this file.\n' > "$context"
      echo "  state    $context (fallback)"
    fi
  fi
}

# ── autoload block management ─────────────────────────────────────────────────

ensure_startup_file() {
  local file="$1" title="$2"
  [[ -f "$file" ]] || printf '# %s\n' "$title" > "$file"
}

# Replaces the block between the markers, or appends it when absent.
write_autoload_block() {
  local file="$1" block_file="$2" tmp
  tmp="$(mktemp)"

  if grep -qF "$BEGIN_MARK" "$file"; then
    awk -v begin_mark="$BEGIN_MARK" -v close_mark="$CLOSE_MARK" -v block_file="$block_file" '
      BEGIN {
        while ((getline line < block_file) > 0) block = block line "\n"
        close(block_file)
        inside = 0
      }
      $0 == begin_mark { printf "%s", block; inside = 1; next }
      $0 == close_mark { inside = 0; next }
      !inside { print }
    ' "$file" > "$tmp"
  else
    cat "$file" > "$tmp"
    if [[ -s "$tmp" ]]; then echo "" >> "$tmp"; fi
    cat "$block_file" >> "$tmp"
  fi

  mv "$tmp" "$file"
  rm -f "$block_file"
  echo "  startup  $file"
}

band_lines() {
  local skills_path="$1" band
  for band in "${BANDS[@]}"; do
    echo "- $skills_path/$band/SKILL.md"
  done
}

# ── per-agent installers ──────────────────────────────────────────────────────

install_claude() {
  echo "Claude:"
  install_commands "$KIT_ROOT/claude/commands" "$REPO_PATH/.claude/commands"
  install_skills   "$KIT_ROOT/claude/skills"   "$REPO_PATH/.claude/skills"

  local file="$REPO_PATH/CLAUDE.md"
  ensure_startup_file "$file" "Claude Instructions"

  local block; block="$(mktemp)"
  cat > "$block" <<DOC
$BEGIN_MARK
Slash commands: load command files from .claude/commands/*.md

Pipeline skills — invoke by name to run a stage:
- survey     → profile the repo into .buildcli/context.md, split into bands
- brief      → requirements with testable acceptance criteria (moves .buildcli/active)
- shape      → architecture and a phased plan
- worklist   → atomic units with dependencies and band tags
- build      → execute the worklist band by band, with progress tracking
- audit      → check the implementation against the brief's acceptance criteria
- patch      → minimal defect fix (add --trace to file a defect blueprint)
- pulse      → read-only pipeline snapshot: stage, unit counts, next step
- focus      → move the active blueprint pointer without re-running brief
- forge      → create or refresh a project-specific skill
- rig        → configure Claude Code hooks and permissions

Band skills — load only the one matching the work in front of you:
$(band_lines ".claude/skills")

Also available:
- .claude/skills/design-review/SKILL.md  → architecture tradeoffs before implementation

Startup behavior (required):
1. Run the \`survey\` skill first to create or refresh \`.buildcli/context.md\`.
2. Refresh it whenever the stack, architecture, integrations, or standards change.
3. Before any task, load only the band skill matching the work: service, interface, store, verify, delivery.
4. Each band skill names the exact block of \`.buildcli/context.md\` to read. Read that block, nothing else.
5. Missing critical information → mark \`NEEDS CLARIFICATION\` and continue on safe defaults.

Shared state:
- \`.buildcli/context.md\`   — project context, split into [band:*] blocks
- \`.buildcli/active\`       — path to the active blueprint directory
- \`blueprints/<kind>/<slug>/\` — brief.md, shape.md, worklist.md, audit.md

Multi-agent relay:
- brief + shape → an analysis-focused agent (Gemini, Claude)
- build → a code-generation agent (Claude, Codex)
- Handoff happens through the files. The relay block at the end of every brief.md says who picks up next.

Bootstrap command:
\`./buildcli/scripts/bootstrap.sh --repo . --agent all --mode copy\`
$CLOSE_MARK
DOC
  write_autoload_block "$file" "$block"
}

install_codex() {
  echo "Codex:"
  install_commands "$KIT_ROOT/codex/commands" "$REPO_PATH/.codex/commands"
  install_skills   "$KIT_ROOT/codex/skills"   "$REPO_PATH/.codex/skills"

  local file="$REPO_PATH/AGENTS.md"
  ensure_startup_file "$file" "Agent Instructions"

  local block; block="$(mktemp)"
  cat > "$block" <<DOC
$BEGIN_MARK
Load command files from .codex/commands/*.md

Band skills — load only the one matching the work in front of you:
$(band_lines ".codex/skills")

Also available:
- .codex/skills/code-standard/SKILL.md  → implementation quality gates and validation evidence

Startup behavior (required):
1. Run \`/survey\` first to create or refresh \`.buildcli/context.md\`.
2. Refresh it whenever the stack, architecture, integrations, or standards change.
3. Before any task, load only the band skill matching the work: service, interface, store, verify, delivery.
4. Each band skill names the exact block of \`.buildcli/context.md\` to read. Read that block, nothing else.
5. Missing critical information → mark \`NEEDS CLARIFICATION\` and continue on safe defaults.

Pipeline order:
1. \`/survey\`    → profile the repo into .buildcli/context.md
2. \`/brief\`     → requirements with acceptance criteria; moves .buildcli/active
3. \`/shape\`     → architecture and a phased plan (reads .buildcli/active)
4. \`/worklist\`  → atomic units with dependencies and band tags
5. \`/build\`     → execute the worklist band by band
6. \`/audit\`     → check the implementation against the brief
7. \`/forge\`     → create or refresh a project-specific skill

Navigation:
- \`/pulse\`  → pipeline snapshot: stage, unit counts, next step
- \`/focus\`  → move the active blueprint pointer
- \`/patch\`  → minimal defect fix; add --trace for a defect blueprint

Shared state:
- \`.buildcli/context.md\`   — project context, split into [band:*] blocks
- \`.buildcli/active\`       — path to the active blueprint directory
- \`blueprints/<kind>/<slug>/\` — brief.md, shape.md, worklist.md, audit.md

Multi-agent relay:
- brief + shape → an analysis-focused agent (Gemini, Claude)
- build → Codex is strongest here: one band, one unit, focused generation
- audit → Gemini for gap analysis, Codex for coverage checks

Bootstrap command:
\`./buildcli/scripts/bootstrap.sh --repo . --agent all --mode copy\`
$CLOSE_MARK
DOC
  write_autoload_block "$file" "$block"
}

install_gemini() {
  echo "Gemini:"
  install_commands "$KIT_ROOT/gemini/commands" "$REPO_PATH/.gemini/commands"
  install_skills   "$KIT_ROOT/gemini/skills"   "$REPO_PATH/.gemini/skills"

  local file="$REPO_PATH/GEMINI.md"
  ensure_startup_file "$file" "Gemini Instructions"

  local block; block="$(mktemp)"
  cat > "$block" <<DOC
$BEGIN_MARK
Load command files from .gemini/commands/*.md

Band skills — load only the one matching the work in front of you:
$(band_lines ".gemini/skills")

Also available:
- .gemini/skills/requirement-split/SKILL.md  → break broad requests into prioritized requirements

Startup behavior (required):
1. Run \`/survey\` first to create or refresh \`.buildcli/context.md\`.
2. Refresh it whenever the stack, architecture, integrations, or standards change.
3. Before any task, load only the band skill matching the work: service, interface, store, verify, delivery.
4. Each band skill names the exact block of \`.buildcli/context.md\` to read. Read that block, nothing else.
5. Missing critical information → mark \`NEEDS CLARIFICATION\` and continue on safe defaults.

Pipeline order:
1. \`/survey\`    → profile the repo into .buildcli/context.md
2. \`/brief\`     → requirements analysis; Gemini's strongest stage
3. \`/shape\`     → architecture and a phased plan (reads .buildcli/active)
4. \`/worklist\`  → atomic units; surface sequencing risk here
5. \`/build\`     → readiness review, then execute or hand off to Claude or Codex
6. \`/audit\`     → deep gap analysis between intent and implementation
7. \`/forge\`     → create or refresh an analysis skill

Navigation:
- \`/pulse\`  → pipeline snapshot with outstanding risk
- \`/focus\`  → move the active blueprint pointer
- \`/patch\`  → root cause analysis and minimal fix; add --trace for a defect blueprint

Shared state:
- \`.buildcli/context.md\`   — project context, split into [band:*] blocks
- \`.buildcli/active\`       — path to the active blueprint directory
- \`blueprints/<kind>/<slug>/\` — brief.md, shape.md, worklist.md, audit.md

Multi-agent relay:
- brief → Gemini preferred; it surfaces the requirements nobody stated
- build → hand off to Claude or Codex once readiness is confirmed
- audit → Gemini again: behavioral drift and edge cases the criteria missed

Bootstrap command:
\`./buildcli/scripts/bootstrap.sh --repo . --agent all --mode copy\`
$CLOSE_MARK
DOC
  write_autoload_block "$file" "$block"
}

install_copilot() {
  echo "Copilot:"
  install_commands "$KIT_ROOT/copilot/commands" "$REPO_PATH/.copilot/commands"
  install_skills   "$KIT_ROOT/copilot/skills"   "$REPO_PATH/.github/skills"

  mkdir -p "$REPO_PATH/.github"
  local file="$REPO_PATH/.github/copilot-instructions.md"
  ensure_startup_file "$file" "Copilot Instructions"

  local block; block="$(mktemp)"
  cat > "$block" <<DOC
$BEGIN_MARK
## Shared state

Every agent on this project reads and writes the same files:

- \`.buildcli/context.md\` — project context, split into independently loadable [band:*] blocks
- \`.buildcli/active\` — path to the active blueprint directory
- \`blueprints/<kind>/<slug>/brief.md\` — requirements and acceptance criteria
- \`blueprints/<kind>/<slug>/shape.md\` — technical plan
- \`blueprints/<kind>/<slug>/worklist.md\` — atomic units with band tags
- \`blueprints/<kind>/<slug>/audit.md\` — verdict per acceptance criterion

## Band skills (auto-discovered)

Skills live in \`.github/skills/\`. Copilot Agent Mode discovers and activates them when the prompt
matches their domain — no manual loading.

$(band_lines ".github/skills")

## Workflow prompts

Copilot has no native slash commands. These are prompt templates: open the file and paste it into
Copilot Chat to run the stage.

- \`.copilot/commands/survey.md\`   → profile the repo into .buildcli/context.md
- \`.copilot/commands/brief.md\`    → requirements with acceptance criteria
- \`.copilot/commands/shape.md\`    → architecture and a phased plan
- \`.copilot/commands/worklist.md\` → atomic units with dependencies and band tags
- \`.copilot/commands/build.md\`    → execute the worklist band by band
- \`.copilot/commands/patch.md\`    → minimal defect fix (add --trace for a blueprint)
- \`.copilot/commands/pulse.md\`    → pipeline snapshot
- \`.copilot/commands/focus.md\`    → move the active blueprint pointer
- \`.copilot/commands/mcp-add.md\`  → add an MCP server to .vscode/mcp.json

## Startup behavior (required)

1. Run the \`survey\` prompt first to create or refresh \`.buildcli/context.md\`.
2. Band skills in \`.github/skills/\` activate automatically in Agent Mode.
3. Each band skill names the exact block of \`.buildcli/context.md\` to read. Read that block, nothing else.
4. Missing critical information → mark \`NEEDS CLARIFICATION\` and continue on safe defaults.

## Multi-agent relay

- survey + brief + shape → an analysis-focused agent
- build → a code-generation agent
- Handoff happens through \`blueprints/<kind>/<slug>/\`, tracked by \`.buildcli/active\`

## Notes

- Band skills are model-agnostic — they work with whatever model backs Copilot.
- Auto-discovery needs Agent Mode (VS Code). In regular chat, paste the skill content by hand.

Bootstrap command:
\`./buildcli/scripts/bootstrap.sh --repo . --agent all --mode copy\`
$CLOSE_MARK
DOC
  write_autoload_block "$file" "$block"
}

# ── run ───────────────────────────────────────────────────────────────────────

echo ""
echo "BuildCLI Agents bootstrap"
echo "  target : $REPO_PATH"
echo "  agent  : $AGENT"
echo "  mode   : $MODE"
echo ""

if [[ "$AGENT" == "claude"  || "$AGENT" == "all" ]]; then install_claude;  fi
if [[ "$AGENT" == "codex"   || "$AGENT" == "all" ]]; then install_codex;   fi
if [[ "$AGENT" == "gemini"  || "$AGENT" == "all" ]]; then install_gemini;  fi
if [[ "$AGENT" == "copilot" || "$AGENT" == "all" ]]; then install_copilot; fi

echo "Shared state:"
ensure_state

echo ""
echo "Done. Installed into $REPO_PATH"
