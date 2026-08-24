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
2. Name the file after the command. Claude/Gemini expose `refactor.md` as `/refactor`; Codex
   pipeline commands are also generated into skills such as `$refactor`.
3. Add it to `CATALOG.md` and to the autoload block in `scripts/bootstrap.sh`.
4. Re-run bootstrap in any project that should get it.

## Generated skills

The Claude and Codex pipeline skills are **derived** from their command files — do not edit them by
hand, the next generation run will overwrite you. A stage is defined once in
`<agent>/commands/<name>.md`. Claude commands carry `skill_description` and `skill_title`; Codex
falls back to the command `description` when no skill-specific description is present.

```bash
python3 buildcli/scripts/generate-skills.py           # regenerate
python3 buildcli/scripts/generate-skills.py --check   # verify, write nothing (runs in CI)
```

`--check` fails on a stale body, a stale description, an orphan skill directory, or a Claude command
missing `skill_description`. It exists because a hand-maintained copy of those descriptions once
kept a renamed path alive through a rename; there is now one source of truth and a job that proves
it.

Band skills (`service`, `interface`, `store`, `verify`, `delivery`) and specialty skills such as
`design-review` and `code-standard` are hand-authored and never generated — the generator knows to
leave them alone.

## Adding a skill

1. Create `<agent>/skills/<name>/SKILL.md` from `_shared/templates/skill-template.md`. For a new
   Claude or Codex *pipeline* skill, write the command instead and generate the skill from it; add
   the name to the generator's hand-authored exemption only if it is genuinely hand-authored.
2. Name the band it reads. A skill that reads more than one band is two skills.
3. Add it to `CATALOG.md`.
4. Re-run bootstrap.

Prefer `/forge` for project-specific skills — it reads real source files and captures the patterns
actually in use, which is the part that makes a skill worth loading.
