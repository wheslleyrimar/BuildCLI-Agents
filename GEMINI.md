# Gemini Instructions

<!-- buildcli:autoload:start -->
Load command files from .gemini/commands/*.md

Band skills — load only the one matching the work in front of you:
- .gemini/skills/service/SKILL.md
- .gemini/skills/interface/SKILL.md
- .gemini/skills/store/SKILL.md
- .gemini/skills/verify/SKILL.md
- .gemini/skills/delivery/SKILL.md

Also available:
- .gemini/skills/requirement-split/SKILL.md  → break broad requests into prioritized requirements

Startup behavior (required):
1. Run `/survey` first to create or refresh `.buildcli/context.md`.
2. Refresh it whenever the stack, architecture, integrations, or standards change.
3. Before any task, load only the band skill matching the work: service, interface, store, verify, delivery.
4. Each band skill names the exact block of `.buildcli/context.md` to read. Read that block, nothing else.
5. Missing critical information → mark `NEEDS CLARIFICATION` and continue on safe defaults.

Pipeline order:
1. `/survey`    → profile the repo into .buildcli/context.md
2. `/brief`     → requirements analysis; Gemini's strongest stage
3. `/shape`     → architecture and a phased plan (reads .buildcli/active)
4. `/worklist`  → atomic units; surface sequencing risk here
5. `/build`     → readiness review, then execute or hand off to Claude or Codex
6. `/audit`     → deep gap analysis between intent and implementation
7. `/forge`     → create or refresh an analysis skill

Navigation:
- `/pulse`  → pipeline snapshot with outstanding risk
- `/focus`  → move the active blueprint pointer
- `/patch`  → root cause analysis and minimal fix; add --trace for a defect blueprint

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
It needs python3. Blocking enforcement hooks are Claude Code only; here the runtime
gives you deterministic band extraction, real scheduling, and executable verification.

Shared state:
- `.buildcli/context.md`   — project context, split into [band:*] blocks
- `.buildcli/active`       — path to the active blueprint directory
- `blueprints/<kind>/<slug>/` — brief.md, shape.md, worklist.md, audit.md

Multi-agent relay:
- brief → Gemini preferred; it surfaces the requirements nobody stated
- build → hand off to Claude or Codex once readiness is confirmed
- audit → Gemini again: behavioral drift and edge cases the criteria missed

Bootstrap command:
`./buildcli/scripts/bootstrap.sh --repo . --agent all --mode copy`
<!-- buildcli:autoload:end -->
