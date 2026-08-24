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
   ```json
   {
     "service": ["src/api/**", "src/services/**"],
     "interface": ["src/components/**", "src/pages/**"],
     "store": ["migrations/**", "src/models/**"],
     "verify": ["tests/**", "**/*.test.*"],
     "delivery": [".github/workflows/**", "Dockerfile", "infra/**"]
   }
   ```
5. Write `.buildcli/enforce.json`:
   ```json
   {
     "enabled": true,
     "context_gate": true,
     "write_gate": true,
     "verify_on_stop": false,
     "session_start": true,
     "journal_max_kb": 256,
     "routing": {},
     "lock_timeout_s": 10
   }
   ```
6. Write the Codex hooks into `.codex/hooks.json`.

   With `--minimal`, install only:
   ```json
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Bash|apply_patch|Edit|Write|mcp__.*",
           "hooks": [{ "type": "command", "command": ".buildcli/runtime/bcx gate post" }]
         }
       ],
       "Stop": [
         { "hooks": [{ "type": "command", "command": ".buildcli/runtime/bcx gate stop" }] }
       ]
     }
   }
   ```

   With `--full`, add:
   ```json
   {
     "matcher": "startup|resume|clear|compact",
     "hooks": [
       {
         "type": "command",
         "command": ".buildcli/runtime/bcx gate session-start",
         "additionalContextLimit": 5000
       }
     ]
   }
   ```
   under `hooks.SessionStart`.

   With `--enforce`, also add:
   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Bash|Read|mcp__.*read.*",
           "hooks": [{ "type": "command", "command": ".buildcli/runtime/bcx gate pre-read" }]
         },
         {
           "matcher": "apply_patch|Edit|Write|mcp__.*write.*",
           "hooks": [{ "type": "command", "command": ".buildcli/runtime/bcx gate pre-write" }]
         }
       ]
     }
   }
   ```
7. Create `.buildcli/journal/` with `.gitkeep` and a `.gitignore` that keeps the directory and ignores `*.log`.
8. Run `.buildcli/runtime/bcx doctor` and report what it says.
9. Tell the user to restart Codex or start a new Codex session so project hooks are loaded, then review and trust the hook definitions when Codex prompts.

## What each gate does

- `pre-read` blocks shell or tool reads of `.buildcli/context.md` and points at `bcx band <name>` or `bcx header`.
- `pre-write` blocks `apply_patch` or write-tool changes to another band's owned paths while one unit is claimed.
- `post` journals edits and test/lint/build commands.
- `stop` writes a checkpoint.
- `session-start` injects `bcx resume` as pointer-only context.

## Rules

- Codex hooks live in `.codex/hooks.json`; do not edit `.claude/settings.json` for this command.
- Project-local Codex hooks must be reviewed/trusted by Codex before they run.
- Do not add Codex rule files unless the user explicitly asks for sandbox/approval defaults.
- The write gate enforces only when a claimed unit gives the caller an unambiguous band.
- Test command still `NEEDS CLARIFICATION` -> leave `verify_on_stop` false and say why.
