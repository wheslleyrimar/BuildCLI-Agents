# Claude

Source for everything BuildCLI Agents installs into `.claude`.

## Contents

- `commands/` — pipeline and navigation commands
- `skills/` — the five band skills, plus `design-review` for architecture tradeoffs

## Installed to

| Source                  | Destination            |
|-------------------------|------------------------|
| `claude/commands/*.md`     | `.claude/commands/` |
| `claude/skills/*/SKILL.md` | `.claude/skills/`   |

Startup file: `CLAUDE.md` — bootstrap writes the autoload block between the
`buildcli:autoload` markers and leaves the rest of the file alone.

## Strength

Broad reasoning and orchestration. Claude carries the full command set, including `rig` — the only stage that touches Claude Code hooks and permissions — and is the only agent that fans `build` out to parallel sub-agents.
