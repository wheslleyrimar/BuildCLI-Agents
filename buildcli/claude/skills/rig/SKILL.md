---
name: rig
description: Wire the Claude Code harness into this project — hooks, band-scoped permissions, and an audit journal in .claude/settings.json.
---

# Rig

## Arguments

(optional) --minimal for hooks only, --full for hooks + permissions + scripts

## Output

.claude/settings.json  |  .buildcli/journal/  |  .buildcli/hooks/session-end.sh.

## Goal

Make every agent session in this project:

- **Recorded** — file changes appended to `.buildcli/journal/session.log`
- **Fenced** — permissions scoped to what the band skills genuinely need
- **Closed out** — a session-end hook that runs the checks before the session disappears

## Steps

1. Read `.buildcli/context.md` and extract:
   - the test command, from `[band:verify]` (e.g. `npm test`, `pytest`, `go test ./...`)
   - the source directories per band, from the Stack and Architecture blocks
   - the CI gate criteria, from `[band:verify]`
2. Read any existing `.claude/settings.json`. Merge into it — never overwrite it.
3. Write `.claude/settings.json` with:

   **Hooks**
   - `PostToolUse` on `Write|Edit|MultiEdit` → append an entry to `.buildcli/journal/session.log`
   - `PostToolUse` on `Bash` → log commands matching `test|lint|build`
   - `Stop` → run `.buildcli/hooks/session-end.sh` when it exists

   **Permissions (`--full` only)**
   - Allow `Bash(git *)`, the test command, the lint command
   - Allow `Read(**)` and `Edit(<src-dirs>/**)`
   - Band-scoped edit rules — service → `src/api/**`, interface → `src/components/**`, and so on

4. Create `.buildcli/journal/` with a `.gitkeep`, plus a `.gitignore` that keeps the directory and ignores `*.log`.
5. Create `.buildcli/hooks/session-end.sh`:
   ```bash
   #!/usr/bin/env bash
   # Runs at the end of every Claude Code session.
   # Extend with: test run, lint check, commit prompt.
   echo "$(date '+%Y-%m-%d %H:%M:%S') | STOP   | session ended" >> .buildcli/journal/session.log
   ```
6. Return: paths touched, permissions configured, anything the user must do by hand.

## settings.json shape

```json
{
  "permissions": {
    "allow": [
      "Bash(git log *)",
      "Bash(git diff *)",
      "Bash(git status)",
      "Bash(<test-command>)",
      "Bash(<lint-command>)"
    ]
  },
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [{
          "type": "command",
          "command": "mkdir -p .buildcli/journal && echo \"$(date '+%Y-%m-%d %H:%M:%S') | EDIT   | $CLAUDE_TOOL_INPUT_FILE_PATH\" >> .buildcli/journal/session.log 2>/dev/null || true"
        }]
      }
    ],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "[ -f .buildcli/hooks/session-end.sh ] && bash .buildcli/hooks/session-end.sh || true"
      }]
    }]
  }
}
```

## Journal format (.buildcli/journal/session.log)

```
2026-08-22 14:32:01 | EDIT   | src/api/checkout.ts
2026-08-22 14:32:15 | EDIT   | src/api/checkout.test.ts
2026-08-22 14:33:00 | STOP   | session ended
```

## Re-running

Safe at any time. It merges with whatever is already in `settings.json` and never drops hand-written
config. Run `--full` on top of a `--minimal` base to layer the band-scoped permissions in later.

## Rules

- Never add a `deny` rule over a path a band skill legitimately needs.
- Test command still `NEEDS CLARIFICATION` → skip the Stop hook and say why.
- Permissions are additive. Append; do not replace.
- Claude Code only. Codex and Gemini do not read `settings.json`.
