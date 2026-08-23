# Gemini

Source for everything BuildCLI Agents installs into `.gemini`.

## Contents

- `commands/` — pipeline and navigation commands
- `skills/` — the five band skills, plus `requirement-split` for breaking down broad requests

## Installed to

| Source                  | Destination            |
|-------------------------|------------------------|
| `gemini/commands/*.md`     | `.gemini/commands/` |
| `gemini/skills/*/SKILL.md` | `.gemini/skills/`   |

Startup file: `GEMINI.md` — bootstrap writes the autoload block between the
`buildcli:autoload` markers and leaves the rest of the file alone.

## Strength

Requirements and gap analysis. Gemini is strongest at `brief` — surfacing the requirements nobody stated — and at `audit`, where behavioral drift and missing edge cases show up.
