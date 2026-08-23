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
  -v, --verbose   List every file installed instead of a summary line per agent.
  --no-banner     Skip the header, for callers that printed one already.
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
VERBOSE="${BUILDCLI_VERBOSE:-0}"
BANNER=1
BEGIN_MARK="<!-- buildcli:autoload:start -->"
CLOSE_MARK="<!-- buildcli:autoload:end -->"

BANDS=(service interface store verify delivery)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)  REPO_PATH="$2"; shift 2 ;;
    --agent) AGENT="$2";     shift 2 ;;
    --mode)  MODE="$2";      shift 2 ;;
    -v|--verbose) VERBOSE=1; shift ;;
    --no-banner)  BANNER=0;  shift ;;
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

# ── output ────────────────────────────────────────────────────────────────────
# One line per agent by default; --verbose restores the full file listing. Color
# is dropped when stdout is not a terminal, so logs and CI stay plain text.

if [[ -t 1 && -z "${NO_COLOR:-}" && "${TERM:-dumb}" != "dumb" ]]; then
  C_RESET=$'\033[0m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'
  C_GREEN=$'\033[32m'; C_CYAN=$'\033[36m'; C_YELLOW=$'\033[33m'
  MARK_OK="✔"
else
  C_RESET=""; C_DIM=""; C_BOLD=""; C_GREEN=""; C_CYAN=""; C_YELLOW=""
  MARK_OK="OK"
fi

TOTAL_FILES=0

# Paths are noise at full length — every one of them starts with $REPO_PATH.
rel() { echo "${1#$REPO_PATH/}"; }

# A file that was written. Counted always, printed only in verbose mode.
tick() {
  local kind="$1" path="$2"
  TOTAL_FILES=$((TOTAL_FILES + 1))
  [[ "$VERBOSE" == "1" ]] && printf '    %s%-8s%s %s\n' "$C_DIM" "$kind" "$C_RESET" "$(rel "$path")"
  return 0
}

# The summary line for a finished component.
done_line() {
  printf '  %s%s%s %s%-9s%s %s\n' \
    "$C_GREEN" "$MARK_OK" "$C_RESET" "$C_BOLD" "$1" "$C_RESET" "$2"
}

warn_line() { printf '  %s!%s %s\n' "$C_YELLOW" "$C_RESET" "$1" >&2; }

# ── file installation ─────────────────────────────────────────────────────────
# Both installers report their count through COUNT, so the caller can build one
# summary line instead of printing per file.

COUNT=0

install_commands() {
  local src_dir="$1" dest_dir="$2" file base dest
  COUNT=0
  [[ -d "$src_dir" ]] || return 0
  mkdir -p "$dest_dir"
  for file in "$src_dir"/*.md; do
    [[ -f "$file" ]] || continue
    base="$(basename "$file")"
    dest="$dest_dir/$base"
    if [[ "$MODE" == "copy" ]]; then cp "$file" "$dest"; else ln -sfn "$file" "$dest"; fi
    tick "command" "$dest"
    COUNT=$((COUNT + 1))
  done
}

install_skills() {
  local src_dir="$1" dest_dir="$2" skill_dir name dest src_file
  COUNT=0
  [[ -d "$src_dir" ]] || return 0
  for skill_dir in "$src_dir"/*/; do
    [[ -d "$skill_dir" ]] || continue
    name="$(basename "$skill_dir")"
    src_file="$skill_dir/SKILL.md"
    [[ -f "$src_file" ]] || continue
    dest="$dest_dir/$name"
    mkdir -p "$dest"
    if [[ "$MODE" == "copy" ]]; then cp "$src_file" "$dest/SKILL.md"; else ln -sfn "$src_file" "$dest/SKILL.md"; fi
    tick "skill" "$dest/SKILL.md"
    COUNT=$((COUNT + 1))
  done
}

# One agent's commands and skills. The summary line waits for its startup file,
# written afterwards, so the counts are held here.
N_CMD=0
N_SKILL=0

agent_files() {
  local label="$1" cmd_src="$2" cmd_dest="$3" skill_src="$4" skill_dest="$5"
  [[ "$VERBOSE" == "1" ]] && printf '  %s%s%s\n' "$C_CYAN" "$label" "$C_RESET"
  install_commands "$cmd_src" "$cmd_dest";   N_CMD="$COUNT"
  install_skills   "$skill_src" "$skill_dest"; N_SKILL="$COUNT"
  return 0
}

agent_done() {
  local label="$1" startup="$2"
  done_line "$label" "$(printf '%2d commands · %2d skills · %s' \
    "$N_CMD" "$N_SKILL" "$(rel "$startup")")"
}

# ── shared state ──────────────────────────────────────────────────────────────

install_runtime() {
  local src="$KIT_ROOT/runtime"
  local dest="$REPO_PATH/.buildcli/runtime"

  [[ -d "$src" ]] || return 0

  mkdir -p "$dest"
  # The runtime is always copied. Symlinking it would break the hook commands
  # recorded in settings.json the moment the source tree moves.
  rm -rf "$dest/bcx_lib"
  cp -R "$src/bcx_lib" "$dest/bcx_lib"
  cp "$src/bcx" "$dest/bcx"
  chmod +x "$dest/bcx"
  find "$dest" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
  tick "runtime" "$dest/bcx"
  # bcx_lib ships as a package. Its modules count toward the total, and get
  # listed like anything else under --verbose.
  local modules=0 module
  while IFS= read -r module; do
    tick "runtime" "$module"
    modules=$((modules + 1))
  done < <(find "$dest/bcx_lib" -type f | sort)
  done_line "Runtime" "$(rel "$dest/bcx") $C_DIM+ $modules modules$C_RESET"

  if ! python3 --version >/dev/null 2>&1; then
    warn_line "python3 not found on PATH — the runtime and its gates will not run."
  fi
}

ensure_state() {
  local context="$REPO_PATH/.buildcli/context.md"
  local template="$KIT_ROOT/_shared/templates/context-template.md"
  local note="blueprints/ · .buildcli/journal/"

  mkdir -p "$REPO_PATH/.buildcli"
  mkdir -p "$REPO_PATH/blueprints/features"
  mkdir -p "$REPO_PATH/blueprints/defects"

  mkdir -p "$REPO_PATH/.buildcli/journal"
  if [[ ! -f "$REPO_PATH/.buildcli/journal/.gitignore" ]]; then
    printf '*.log\n!.gitignore\n' > "$REPO_PATH/.buildcli/journal/.gitignore"
    tick "state" "$REPO_PATH/.buildcli/journal/.gitignore"
  fi

  # The runtime belongs in the target project's history: settings.json hooks point at
  # .buildcli/runtime/bcx, so a teammate who clones without it gets broken hooks.
  if [[ ! -f "$REPO_PATH/.buildcli/.gitignore" ]]; then
    cat > "$REPO_PATH/.buildcli/.gitignore" <<'IGNORE'
# Commit the runtime and the context; keep local state out.
journal/*.log
active
enforce.json
__pycache__/
IGNORE
    tick "state" "$REPO_PATH/.buildcli/.gitignore"
  fi

  if [[ -f "$context" ]]; then
    note="$note · context.md kept"
  elif [[ -f "$template" ]]; then
    cp "$template" "$context"
    tick "state" "$context"
    note="$note · context.md (empty, run survey)"
  else
    printf '# Project Context\n\nTODO: run the `survey` skill to populate this file.\n' > "$context"
    tick "state" "$context"
    note="$note · context.md (fallback)"
  fi

  done_line "State" "$note"
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
  tick "startup" "$file"
}

band_lines() {
  local skills_path="$1" band
  for band in "${BANDS[@]}"; do
    echo "- $skills_path/$band/SKILL.md"
  done
}

# ── per-agent installers ──────────────────────────────────────────────────────

install_claude() {
  agent_files "Claude" "$KIT_ROOT/claude/commands" "$REPO_PATH/.claude/commands" \
              "$KIT_ROOT/claude/skills"   "$REPO_PATH/.claude/skills"

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

Runtime (always prefer it over reading state files by hand):
- \`.buildcli/runtime/bcx band <name>\`   — load exactly one context band
- \`.buildcli/runtime/bcx header\`        — the shared header, without any band
- \`.buildcli/runtime/bcx active [path]\` — read or move the active blueprint pointer
- \`.buildcli/runtime/bcx next\`          — units ready to start, grouped by band
- \`.buildcli/runtime/bcx graph\`         — dependency graph, critical path, cycle report
- \`.buildcli/runtime/bcx claim|done|block <id>\` — unit state transitions
- \`.buildcli/runtime/bcx verify\`        — run the project's test command
- \`.buildcli/runtime/bcx status --json\` — pipeline snapshot
- \`.buildcli/runtime/bcx doctor\`        — validate context, graph, and configuration

Invoke it by that path, not as a bare \`bcx\` — it is project-local and not on PATH.
With \`rig --enforce\` applied, reading \`.buildcli/context.md\` directly is blocked
by a PreToolUse hook.

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
  agent_done "Claude" "$file"
}

install_codex() {
  agent_files "Codex" "$KIT_ROOT/codex/commands" "$REPO_PATH/.codex/commands" \
              "$KIT_ROOT/codex/skills"   "$REPO_PATH/.codex/skills"

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

Runtime (always prefer it over reading state files by hand):
- \`.buildcli/runtime/bcx band <name>\`   — load exactly one context band
- \`.buildcli/runtime/bcx header\`        — the shared header, without any band
- \`.buildcli/runtime/bcx active [path]\` — read or move the active blueprint pointer
- \`.buildcli/runtime/bcx next\`          — units ready to start, grouped by band
- \`.buildcli/runtime/bcx graph\`         — dependency graph, critical path, cycle report
- \`.buildcli/runtime/bcx claim|done|block <id>\` — unit state transitions
- \`.buildcli/runtime/bcx verify\`        — run the project's test command
- \`.buildcli/runtime/bcx status --json\` — pipeline snapshot
- \`.buildcli/runtime/bcx doctor\`        — validate context, graph, and configuration

Invoke it by that path, not as a bare \`bcx\` — it is project-local and not on PATH.
It needs python3. Blocking enforcement hooks are Claude Code only; here the runtime
gives you deterministic band extraction, real scheduling, and executable verification.

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
  agent_done "Codex" "$file"
}

install_gemini() {
  agent_files "Gemini" "$KIT_ROOT/gemini/commands" "$REPO_PATH/.gemini/commands" \
              "$KIT_ROOT/gemini/skills"   "$REPO_PATH/.gemini/skills"

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

Runtime (always prefer it over reading state files by hand):
- \`.buildcli/runtime/bcx band <name>\`   — load exactly one context band
- \`.buildcli/runtime/bcx header\`        — the shared header, without any band
- \`.buildcli/runtime/bcx active [path]\` — read or move the active blueprint pointer
- \`.buildcli/runtime/bcx next\`          — units ready to start, grouped by band
- \`.buildcli/runtime/bcx graph\`         — dependency graph, critical path, cycle report
- \`.buildcli/runtime/bcx claim|done|block <id>\` — unit state transitions
- \`.buildcli/runtime/bcx verify\`        — run the project's test command
- \`.buildcli/runtime/bcx status --json\` — pipeline snapshot
- \`.buildcli/runtime/bcx doctor\`        — validate context, graph, and configuration

Invoke it by that path, not as a bare \`bcx\` — it is project-local and not on PATH.
It needs python3. Blocking enforcement hooks are Claude Code only; here the runtime
gives you deterministic band extraction, real scheduling, and executable verification.

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
  agent_done "Gemini" "$file"
}

install_copilot() {
  agent_files "Copilot" "$KIT_ROOT/copilot/commands" "$REPO_PATH/.copilot/commands" \
              "$KIT_ROOT/copilot/skills"   "$REPO_PATH/.github/skills"

  mkdir -p "$REPO_PATH/.github"
  local file="$REPO_PATH/.github/copilot-instructions.md"
  ensure_startup_file "$file" "Copilot Instructions"

  local block; block="$(mktemp)"
  cat > "$block" <<DOC
$BEGIN_MARK
## Runtime

A project-local executable at \`.buildcli/runtime/bcx\` (needs python3). Prefer it over
reading state files by hand:

- \`.buildcli/runtime/bcx band <name>\` — load exactly one context band
- \`.buildcli/runtime/bcx next\` — units ready to start, grouped by band
- \`.buildcli/runtime/bcx graph\` — dependency graph and cycle report
- \`.buildcli/runtime/bcx claim|done|block <id>\` — unit state transitions
- \`.buildcli/runtime/bcx verify\` — run the project's test command
- \`.buildcli/runtime/bcx doctor\` — validate context, graph, and configuration

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
  agent_done "Copilot" "$file"
}

# ── run ───────────────────────────────────────────────────────────────────────

if [[ "$BANNER" == "1" ]]; then
  printf '\n%sBuildCLI Agents%s %sbootstrap%s\n' "$C_BOLD" "$C_RESET" "$C_DIM" "$C_RESET"
  printf '  %s%s%s\n' "$C_DIM" "$REPO_PATH" "$C_RESET"
  printf '  %sagent %s · mode %s%s\n\n' "$C_DIM" "$AGENT" "$MODE" "$C_RESET"
fi

if [[ "$AGENT" == "claude"  || "$AGENT" == "all" ]]; then install_claude;  fi
if [[ "$AGENT" == "codex"   || "$AGENT" == "all" ]]; then install_codex;   fi
if [[ "$AGENT" == "gemini"  || "$AGENT" == "all" ]]; then install_gemini;  fi
if [[ "$AGENT" == "copilot" || "$AGENT" == "all" ]]; then install_copilot; fi

install_runtime
ensure_state

printf '\n%sDone.%s %s%d files into %s%s\n' \
  "$C_BOLD" "$C_RESET" "$C_DIM" "$TOTAL_FILES" "$REPO_PATH" "$C_RESET"
[[ "$VERBOSE" == "1" ]] || \
  printf '%s      --verbose lists every one of them.%s\n' "$C_DIM" "$C_RESET"
