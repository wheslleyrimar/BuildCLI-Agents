# Agent Instructions

<!-- buildcli:autoload:start -->
Codex pipeline skills are generated from .codex/commands/*.md and invoked with `$name`:
- $survey    → profile the repo into .buildcli/context.md
- $brief     → requirements with acceptance criteria; moves .buildcli/active
- $shape     → architecture and a phased plan (reads .buildcli/active)
- $worklist  → atomic units with dependencies and band tags
- $build     → execute the worklist band by band
- $audit     → check the implementation against the brief
- $forge     → create or refresh a project-specific skill

Band skills — load only the one matching the work in front of you:
- .codex/skills/service/SKILL.md
- .codex/skills/interface/SKILL.md
- .codex/skills/store/SKILL.md
- .codex/skills/verify/SKILL.md
- .codex/skills/delivery/SKILL.md

Also available:
- .codex/skills/code-standard/SKILL.md  → implementation quality gates and validation evidence
- .codex/skills/rig/SKILL.md            → Codex hooks, band path map, and audit journal

Startup behavior (required):
1. Run `$survey` first to create or refresh `.buildcli/context.md`.
2. Refresh it whenever the stack, architecture, integrations, or standards change.
3. Before any task, load only the band skill matching the work: service, interface, store, verify, delivery.
4. Each band skill names the exact block of `.buildcli/context.md` to read. Read that block, nothing else.
5. Missing critical information → mark `NEEDS CLARIFICATION` and continue on safe defaults.

Pipeline order:
1. `$survey`    → profile the repo into .buildcli/context.md
2. `$brief`     → requirements with acceptance criteria; moves .buildcli/active
3. `$shape`     → architecture and a phased plan (reads .buildcli/active)
4. `$worklist`  → atomic units with dependencies and band tags
5. `$build`     → execute the worklist band by band
6. `$audit`     → check the implementation against the brief
7. `$forge`     → create or refresh a project-specific skill

Navigation:
- `$pulse`  → pipeline snapshot: stage, unit counts, next step
- `$focus`  → move the active blueprint pointer
- `$patch`  → minimal defect fix; add --trace for a defect blueprint
- `$rig`    → configure Codex hooks and the audit journal

Runtime (always prefer it over reading state files by hand):
- `.buildcli/runtime/bcx band <name>`   — load exactly one context band
- `.buildcli/runtime/bcx header`        — the shared header, without any band
- `.buildcli/runtime/bcx active [path]` — read or move the active blueprint pointer
- `.buildcli/runtime/bcx next`          — units ready to start, grouped by band
- `.buildcli/runtime/bcx graph`         — dependency graph, critical path, cycle report
- `.buildcli/runtime/bcx claim|done|block <id>` — unit state transitions
- `.buildcli/runtime/bcx verify`        — run the project's test command
- `.buildcli/runtime/bcx status --json` — pipeline snapshot
- `.buildcli/runtime/bcx resume`        — where the project left off, in one screen
- `.buildcli/runtime/bcx doctor`        — validate context, graph, and configuration

Invoke it by that path, not as a bare `bcx` — it is project-local and not on PATH.
It needs python3. With `$rig --enforce`, Codex hooks call `bcx gate` to block raw
context reads and cross-band writes. Without hooks, the runtime still gives you
deterministic band extraction, real scheduling, and executable verification.

Shared state:
- `.buildcli/context.md`   — project context, split into [band:*] blocks
- `.buildcli/active`       — path to the active blueprint directory
- `.codex/hooks.json`      — Codex lifecycle hooks written by `$rig`
- `blueprints/<kind>/<slug>/` — brief.md, shape.md, worklist.md, audit.md

Multi-agent relay:
- brief + shape → an analysis-focused agent (Gemini, Claude)
- build → Codex is strongest here: one band, one unit, focused generation
- audit → Gemini for gap analysis, Codex for coverage checks

Bootstrap command:
`./buildcli/scripts/bootstrap.sh --repo . --agent all --mode copy`
<!-- buildcli:autoload:end -->
