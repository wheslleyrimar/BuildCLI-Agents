# Codex

Source for everything BuildCLI Agents installs into `.codex`.

## Contents

- `commands/` — source prompts for pipeline, navigation, and Codex rig workflows
- `skills/` — the five band skills, `code-standard`, and generated pipeline skills

Codex does not turn `.codex/commands/*.md` into custom slash commands. The pipeline commands are
also generated as skills, so users invoke them as `$survey`, `$brief`, `$shape`, `$worklist`,
`$build`, `$audit`, `$pulse`, `$focus`, `$patch`, `$forge`, and `$rig`.

## Installed to

| Source                  | Destination            |
|-------------------------|------------------------|
| `codex/commands/*.md`     | `.codex/commands/` |
| `codex/skills/*/SKILL.md` | `.codex/skills/`   |

Startup file: `AGENTS.md` — bootstrap writes the autoload block between the
`buildcli:autoload` markers and leaves the rest of the file alone.

## Strength

Focused code generation with local lifecycle hooks. Codex is strongest at `build` and `patch`:
one band, one unit, a working change with validation attached. `$rig --enforce` wires
`.codex/hooks.json` to the shared `bcx gate` runtime.
