---
name: rig
description: Wire the enforcing harness into this project — runtime, blocking PreToolUse gates, band path map, and the audit journal.
---

# Rig

## Arguments

(optional) --minimal (journal only) | --full (default: journal + permissions) | --enforce (adds the blocking gates)

## Output

.claude/settings.json | .buildcli/bands.json | .buildcli/enforce.json | .buildcli/journal/.
## Goal

Turn the band rule from a convention the model is asked to follow into a constraint the runtime
applies. Three levels, each additive:

| Level | What it does |
|---|---|
| `--minimal` | journals every edit |
| `--full` | journal + scoped permissions (default) |
| `--enforce` | the above, plus `PreToolUse` gates that **block** out-of-band reads and writes |

## Steps

1. Confirm the runtime is present at `.buildcli/runtime/bcx`. Missing → tell the user to
   re-run the bootstrap script; the gates cannot work without it.
2. Read the context through the runtime — `.buildcli/runtime/bcx band verify` and `.buildcli/runtime/bcx header`, never by
   opening the file — and extract:
   - the test command from `[band:verify]`
   - the source directories per band, from the Stack and Architecture blocks
3. Read any existing `.claude/settings.json`. Merge into it; never overwrite it.
4. Write `.buildcli/bands.json` — the band path map the write gate reads. Derive the globs from
   the real directory layout, and show them to the user for confirmation. A band with no entry is
   simply not enforced.
   ```json
   {
     "service":   ["src/api/**", "src/services/**"],
     "interface": ["src/components/**", "src/pages/**"],
     "store":     ["migrations/**", "src/models/**"],
     "verify":    ["tests/**", "**/*.test.*"],
     "delivery":  [".github/workflows/**", "Dockerfile", "infra/**"]
   }
   ```
5. Write `.buildcli/enforce.json` so the gates can be tuned without editing `settings.json`:
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
   Every key is defaulted in the runtime, so an older `enforce.json` keeps working. `session_start`
   controls the resume digest and `journal_max_kb` the journal's rotation size. `routing` maps a band
   to the agent best suited to it — read only by `bcx next`, and an empty table simply means no
   recommendation. `lock_timeout_s` is how long a unit transition waits for the worklist mutex before
   giving up; it is not a staleness threshold, and the runtime derives that separately on purpose.
6. Write the hooks into `.claude/settings.json` (see below).
7. Create `.buildcli/journal/` with a `.gitkeep` and a `.gitignore` that keeps the directory and
   ignores `*.log`.
8. Run `.buildcli/runtime/bcx doctor` and report what it says.
9. Return: files touched, the level applied, and anything the user must decide.

## settings.json — with `--enforce`

```json
{
  "permissions": {
    "allow": [
      "Bash(.buildcli/runtime/bcx *)",
      "Bash(git log *)",
      "Bash(git diff *)",
      "Bash(git status)",
      "Bash(<test-command>)",
      "Bash(<lint-command>)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Read",
        "hooks": [{ "type": "command", "command": ".buildcli/runtime/bcx gate pre-read" }]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [{ "type": "command", "command": ".buildcli/runtime/bcx gate pre-write" }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit|Bash",
        "hooks": [{ "type": "command", "command": ".buildcli/runtime/bcx gate post" }]
      }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": ".buildcli/runtime/bcx gate stop" }] }
    ],
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": ".buildcli/runtime/bcx gate session-start" }] }
    ]
  }
}
```

`SessionStart` carries no matcher on purpose. It accepts `startup`, `resume`, `clear`, `compact`,
and `fork`; omitting it covers all five, and a compaction is exactly when restating the pointers is
worth the thirty lines.

Without `--enforce`, omit the `PreToolUse` block and keep the rest.

## What each gate does

- **`pre-read`** — blocks a raw `Read` of `.buildcli/context.md` and points at `.buildcli/runtime/bcx band <name>`.
  This is what makes band scoping real: the whole file cannot be loaded.
- **`pre-write`** — while exactly one unit is claimed (`.buildcli/runtime/bcx claim <id>`), blocks writes to paths
  that `bands.json` assigns to a *different* band. Paths no band claims are always allowed, so docs
  and root config stay editable.
- **`post`** — appends to `.buildcli/journal/session.log`, rotating it past `journal_max_kb`.
- **`stop`** — journals a checkpoint naming the active blueprint, the claimed units, how many units
  completed during the session, and the verify outcome. Runs `.buildcli/runtime/bcx verify` first when
  `verify_on_stop` is true.
- **`session-start`** — prints `.buildcli/runtime/bcx resume` on stdout, which Claude Code adds as context, so a
  new session opens knowing where the pipeline stands. Pointers only, never band content — a digest
  carrying band text would defeat `pre-read` from the inside. That takes two mechanisms: the digest
  never reads `context.md`, and VERIFY journal lines are trimmed before the command, because that
  command was read out of `[band:verify]`. Silenced with `session_start: false`.

Every gate fails open. Malformed input, a missing map, an internal error — the call is allowed. A
harness that breaks the session on its own bug is worse than no harness.

## Journal format

```
2026-08-22 14:32:01 | EDIT   | Edit      src/api/checkout.ts
2026-08-22 14:32:40 | DONE   | W03 -> done (service)
2026-08-22 14:33:02 | VERIFY | PASS exit=0 :: npm test
2026-08-22 14:33:05 | STOP   | blueprint=blueprints/features/checkout claimed=- completed=3 verify=pass
```

The `STOP` line is what the next session reads back. `CLAIM`, `DONE`, and `BLOCK` carry the unit
transitions, so completions can be counted between two `STOP` lines without parsing prose.

## For the human

The hooks and skills all use `.buildcli/runtime/bcx`. Offer the user the shim so they can type
`bcx` themselves:

```bash
.buildcli/runtime/bcx shim --install
```

## Turning it off

`.buildcli/enforce.json` is the switch — set `enabled: false` to disable every gate without
touching `settings.json`, or turn off `context_gate` / `write_gate` individually.

## Re-running

Safe at any time. Merges with existing config and never drops hand-written entries. Run `--enforce`
on top of a `--full` base to add the gates later.

## Rules

- Never add a `deny` rule over a path a band skill legitimately needs.
- The write gate only fires while a single unit is claimed. Ambiguity means no enforcement, by design.
- Test command still `NEEDS CLARIFICATION` → leave `verify_on_stop` false and say why.
- Permissions are additive. Append; never replace.
- Claude Code only. Codex has its own `rig` command that writes `.codex/hooks.json`; Gemini and
  Copilot use the runtime, but have no blocking hooks.
