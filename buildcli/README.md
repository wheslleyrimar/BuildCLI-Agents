# buildcli/ — the kit

This folder is the source of everything BuildCLI Agents installs. It is **not** copied into target projects;
bootstrap reads from here and writes into the target's native agent folders.

- `claude/`, `codex/`, `gemini/`, `copilot/` — commands and skills per agent
- `_shared/templates/` — the templates bootstrap and `/forge` start from
- `scripts/bootstrap.sh` — the installer
- `ROUTING.md` — where every file lands and why
- `CATALOG.md` — every command and skill, with inputs and outputs

## Adding a command

1. Copy `_shared/templates/command-template.md` into the agent's `commands/` folder.
2. Name the file after the command: `refactor.md` becomes `/refactor`.
3. Add it to `CATALOG.md` and to the autoload block in `scripts/bootstrap.sh`.
4. Re-run bootstrap in any project that should get it.

## Adding a skill

1. Create `<agent>/skills/<name>/SKILL.md` from `_shared/templates/skill-template.md`.
2. Name the band it reads. A skill that reads more than one band is two skills.
3. Add it to `CATALOG.md`.
4. Re-run bootstrap.

Prefer `/forge` for project-specific skills — it reads real source files and captures the patterns
actually in use, which is the part that makes a skill worth loading.
