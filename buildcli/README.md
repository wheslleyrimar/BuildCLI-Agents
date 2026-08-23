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

## Generated skills

The eleven Claude pipeline skills are **derived** from their command files — do not edit them by
hand, the next generation run will overwrite you. A stage is defined once in
`claude/commands/<name>.md`, whose frontmatter carries `skill_description` and `skill_title`
alongside the command fields.

```bash
python3 buildcli/scripts/generate-skills.py           # regenerate
python3 buildcli/scripts/generate-skills.py --check   # verify, write nothing (runs in CI)
```

`--check` fails on a stale body, a stale description, an orphan skill directory, or a command
missing `skill_description`. It exists because a hand-maintained copy of those descriptions once
kept a renamed path alive through a rename; there is now one source of truth and a job that proves
it.

Band skills (`service`, `interface`, `store`, `verify`, `delivery`) and `design-review` are
hand-authored and never generated — the generator knows to leave them alone.

## Adding a skill

1. Create `<agent>/skills/<name>/SKILL.md` from `_shared/templates/skill-template.md`. For a new
   Claude *pipeline* skill, write the command instead and generate the skill from it; add the name
   to `NOT_GENERATED` in the generator only if it is genuinely hand-authored.
2. Name the band it reads. A skill that reads more than one band is two skills.
3. Add it to `CATALOG.md`.
4. Re-run bootstrap.

Prefer `/forge` for project-specific skills — it reads real source files and captures the patterns
actually in use, which is the part that makes a skill worth loading.
