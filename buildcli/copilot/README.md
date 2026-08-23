# Copilot

Source for everything BuildCLI Agents installs for GitHub Copilot.

## Contents

- `commands/` — prompt templates. Copilot has no native slash commands: open a file and paste it into Copilot Chat.
- `skills/` — the five band skills

## Installed to

| Source                     | Destination         |
|----------------------------|---------------------|
| `copilot/commands/*.md`     | `.copilot/commands/` |
| `copilot/skills/*/SKILL.md` | `.github/skills/`    |

Skills go to `.github/skills/` because that is where Copilot Agent Mode auto-discovers them in
VS Code. In regular chat there is no discovery — paste the skill content by hand.

Startup file: `.github/copilot-instructions.md` — bootstrap writes the autoload block between the
`buildcli:autoload` markers and leaves the rest of the file alone.

## Strength

In-editor and model-agnostic. The band skills work with whatever model backs Copilot, which makes
this the right surface for `build` and `patch` while you are already in the file.

## Extra

`mcp-add.md` walks you through adding an MCP server to `.vscode/mcp.json` without hardcoding a secret.
