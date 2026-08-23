# Codex

Source for everything BuildCLI Agents installs into `.codex`.

## Contents

- `commands/` — pipeline and navigation commands
- `skills/` — the five band skills, plus `code-standard` for implementation quality gates

## Installed to

| Source                  | Destination            |
|-------------------------|------------------------|
| `codex/commands/*.md`     | `.codex/commands/` |
| `codex/skills/*/SKILL.md` | `.codex/skills/`   |

Startup file: `AGENTS.md` — bootstrap writes the autoload block between the
`buildcli:autoload` markers and leaves the rest of the file alone.

## Strength

Focused code generation. Codex is strongest at `build` and `patch`: one band, one unit, a working change with validation attached.
