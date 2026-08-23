# Claude Instructions

<!-- buildcli:autoload:start -->
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
- .claude/skills/service/SKILL.md
- .claude/skills/interface/SKILL.md
- .claude/skills/store/SKILL.md
- .claude/skills/verify/SKILL.md
- .claude/skills/delivery/SKILL.md

Also available:
- .claude/skills/design-review/SKILL.md  → architecture tradeoffs before implementation

Startup behavior (required):
1. Run the `survey` skill first to create or refresh `.buildcli/context.md`.
2. Refresh it whenever the stack, architecture, integrations, or standards change.
3. Before any task, load only the band skill matching the work: service, interface, store, verify, delivery.
4. Each band skill names the exact block of `.buildcli/context.md` to read. Read that block, nothing else.
5. Missing critical information → mark `NEEDS CLARIFICATION` and continue on safe defaults.

Runtime (always prefer it over reading state files by hand):
- `.buildcli/runtime/bcx band <name>`   — load exactly one context band
- `.buildcli/runtime/bcx header`        — the shared header, without any band
- `.buildcli/runtime/bcx active [path]` — read or move the active blueprint pointer
- `.buildcli/runtime/bcx next`          — units ready to start, grouped by band
- `.buildcli/runtime/bcx graph`         — dependency graph, critical path, cycle report
- `.buildcli/runtime/bcx claim|done|block <id>` — unit state transitions
- `.buildcli/runtime/bcx verify`        — run the project's test command
- `.buildcli/runtime/bcx status --json` — pipeline snapshot
- `.buildcli/runtime/bcx doctor`        — validate context, graph, and configuration

Invoke it by that path, not as a bare `bcx` — it is project-local and not on PATH.
With `rig --enforce` applied, reading `.buildcli/context.md` directly is blocked
by a PreToolUse hook.

Shared state:
- `.buildcli/context.md`   — project context, split into [band:*] blocks
- `.buildcli/active`       — path to the active blueprint directory
- `blueprints/<kind>/<slug>/` — brief.md, shape.md, worklist.md, audit.md

Multi-agent relay:
- brief + shape → an analysis-focused agent (Gemini, Claude)
- build → a code-generation agent (Claude, Codex)
- Handoff happens through the files. The relay block at the end of every brief.md says who picks up next.

Bootstrap command:
`./buildcli/scripts/bootstrap.sh --repo . --agent all --mode copy`
<!-- buildcli:autoload:end -->
