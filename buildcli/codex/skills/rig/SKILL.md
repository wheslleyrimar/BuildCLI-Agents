---
name: rig
description: Wire Codex hooks into this project - runtime gates, band path map, resume context, and the audit journal.
---

# Rig

## Arguments

(optional) --minimal (journal only) | --full (default: journal + resume) | --enforce (adds blocking gates)

## Output

.codex/hooks.json | .buildcli/bands.json | .buildcli/enforce.json | .buildcli/journal/.

## Goal

Turn the band rule from Codex guidance into project-local hooks. Three levels, each additive:

| Level | What it does |
|---|---|
| `--minimal` | journals edits and Stop checkpoints |
| `--full` | journal + SessionStart resume digest (default) |
| `--enforce` | the above, plus `PreToolUse` gates that block raw context reads and cross-band writes |

## Steps

1. Confirm the runtime exists at `.buildcli/runtime/bcx`. Missing -> tell the user to re-run bootstrap.
2. Read context only through the runtime:
   ```bash
   .buildcli/runtime/bcx header
   .buildcli/runtime/bcx band verify
   ```
   Extract the test command from `[band:verify]` and the source directories from the header.
3. Read any existing `.codex/hooks.json`. Merge into it; never overwrite unrelated hooks.
4. Write `.buildcli/bands.json`, deriving globs from the real layout. A band with no entry is not enforced.
5. Write `.buildcli/enforce.json` with defaults for `enabled`, `context_gate`, `write_gate`, `verify_on_stop`, `session_start`, `journal_max_kb`, `routing`, and `lock_timeout_s`.
6. Write the Codex hooks into `.codex/hooks.json`.
   - `--minimal`: `PostToolUse` runs `.buildcli/runtime/bcx gate post`; `Stop` runs `.buildcli/runtime/bcx gate stop`.
   - `--full`: add `SessionStart` for `startup|resume|clear|compact`, running `.buildcli/runtime/bcx gate session-start` with `additionalContextLimit: 5000`.
   - `--enforce`: add `PreToolUse` hooks. `Bash|Read|mcp__.*read.*` runs `pre-read`; `apply_patch|Edit|Write|mcp__.*write.*` runs `pre-write`.
7. Create `.buildcli/journal/` with `.gitkeep` and a `.gitignore` that keeps the directory and ignores `*.log`.
8. Run `.buildcli/runtime/bcx doctor` and report what it says.
9. Tell the user to restart Codex or start a new Codex session so project hooks are loaded, then review and trust the hook definitions when Codex prompts.

## Rules

- Codex hooks live in `.codex/hooks.json`; do not edit `.claude/settings.json` for this skill.
- Project-local Codex hooks must be reviewed/trusted by Codex before they run.
- Do not add Codex rule files unless the user explicitly asks for sandbox/approval defaults.
- The write gate enforces only when a claimed unit gives the caller an unambiguous band.
- Test command still `NEEDS CLARIFICATION` -> leave `verify_on_stop` false and say why.
