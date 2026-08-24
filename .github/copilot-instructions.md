# Copilot Instructions

<!-- buildcli:autoload:start -->
## Runtime

A project-local executable at `.buildcli/runtime/bcx` (needs python3). Prefer it over
reading state files by hand:

- `.buildcli/runtime/bcx band <name>` — load exactly one context band
- `.buildcli/runtime/bcx next` — units ready to start, grouped by band
- `.buildcli/runtime/bcx graph` — dependency graph and cycle report
- `.buildcli/runtime/bcx claim|done|block <id>` — unit state transitions
- `.buildcli/runtime/bcx verify` — run the project's test command
- `.buildcli/runtime/bcx resume` — where the project left off, in one screen
- `.buildcli/runtime/bcx doctor` — validate context, graph, and configuration

## Shared state

Every agent on this project reads and writes the same files:

- `.buildcli/context.md` — project context, split into independently loadable [band:*] blocks
- `.buildcli/active` — path to the active blueprint directory
- `blueprints/<kind>/<slug>/brief.md` — requirements and acceptance criteria
- `blueprints/<kind>/<slug>/shape.md` — technical plan
- `blueprints/<kind>/<slug>/worklist.md` — atomic units with band tags
- `blueprints/<kind>/<slug>/audit.md` — verdict per acceptance criterion

## Band skills (auto-discovered)

Skills live in `.github/skills/`. Copilot Agent Mode discovers and activates them when the prompt
matches their domain — no manual loading.

- .github/skills/service/SKILL.md
- .github/skills/interface/SKILL.md
- .github/skills/store/SKILL.md
- .github/skills/verify/SKILL.md
- .github/skills/delivery/SKILL.md

## Workflow prompts

Copilot has no native slash commands. These are prompt templates: open the file and paste it into
Copilot Chat to run the stage.

- `.copilot/commands/survey.md`   → profile the repo into .buildcli/context.md
- `.copilot/commands/brief.md`    → requirements with acceptance criteria
- `.copilot/commands/shape.md`    → architecture and a phased plan
- `.copilot/commands/worklist.md` → atomic units with dependencies and band tags
- `.copilot/commands/build.md`    → execute the worklist band by band
- `.copilot/commands/patch.md`    → minimal defect fix (add --trace for a blueprint)
- `.copilot/commands/pulse.md`    → pipeline snapshot
- `.copilot/commands/focus.md`    → move the active blueprint pointer
- `.copilot/commands/mcp-add.md`  → add an MCP server to .vscode/mcp.json

## Startup behavior (required)

1. Run the `survey` prompt first to create or refresh `.buildcli/context.md`.
2. Band skills in `.github/skills/` activate automatically in Agent Mode.
3. Each band skill names the exact block of `.buildcli/context.md` to read. Read that block, nothing else.
4. Missing critical information → mark `NEEDS CLARIFICATION` and continue on safe defaults.

## Multi-agent relay

- survey + brief + shape → an analysis-focused agent
- build → a code-generation agent
- Handoff happens through `blueprints/<kind>/<slug>/`, tracked by `.buildcli/active`

## Notes

- Band skills are model-agnostic — they work with whatever model backs Copilot.
- Auto-discovery needs Agent Mode (VS Code). In regular chat, paste the skill content by hand.

Bootstrap command:
`./buildcli/scripts/bootstrap.sh --repo . --agent all --mode copy`
<!-- buildcli:autoload:end -->
