# Routing

Folder names alone do not wire anything up. Each agent runtime looks in its own place for
commands and skills, and reads its own startup file. Bootstrap puts the right files in the
right folders and writes the autoload block into each startup file.

## Layout in a target project (after bootstrap)

```
<project-root>/
├── .claude/
│   ├── commands/                 ← loaded natively by Claude Code
│   └── skills/
├── .codex/
│   ├── commands/                 ← source prompts, generated into pipeline skills
│   ├── skills/                   ← invoked as $survey, $brief, ...
│   └── hooks.json                ← optional, written by Codex rig
├── .gemini/
│   ├── commands/                 ← loaded natively by Gemini
│   └── skills/
├── .copilot/
│   └── commands/                 ← prompt templates, pasted into Copilot Chat
├── .github/
│   ├── skills/                   ← auto-discovered by Copilot Agent Mode
│   └── copilot-instructions.md   ← Copilot startup file
├── .buildcli/
│   ├── context.md                ← shared context, split into [band:*] blocks
│   ├── active                    ← path to the active blueprint
│   ├── journal/session.log       ← audit trail (written by rig hooks)
│   └── runtime/bcx               ← `bcx gate stop` closes each hooked session
├── blueprints/
│   ├── features/<slug>/          ← brief.md · shape.md · worklist.md · audit.md
│   └── defects/<slug>/
├── CLAUDE.md                     ← Claude startup file
├── AGENTS.md                     ← Codex startup file
└── GEMINI.md                     ← Gemini startup file
```

The `buildcli/` kit folder stays in this source repository. It is never copied into a target project.

## Native paths per agent (target project)

| Agent   | Commands                  | Skills                        | Startup file                     |
|---------|---------------------------|-------------------------------|----------------------------------|
| Claude  | `.claude/commands/*.md`   | `.claude/skills/*/SKILL.md`   | `CLAUDE.md`                      |
| Codex   | `.codex/commands/*.md` ³  | `.codex/skills/*/SKILL.md`    | `AGENTS.md`                      |
| Gemini  | `.gemini/commands/*.md`   | `.gemini/skills/*/SKILL.md`   | `GEMINI.md`                      |
| Copilot | `.copilot/commands/*.md` ¹| `.github/skills/*/SKILL.md` ² | `.github/copilot-instructions.md`|

¹ Copilot has no native slash commands. These files are prompt templates — open one, paste it into Copilot Chat.
² Skills under `.github/skills/` are auto-discovered by Copilot Agent Mode in VS Code. In regular chat, paste the content by hand.
³ Codex uses these as source prompts; the same workflows are generated into skills and invoked as `$name`.

## Source paths (this repository)

| Agent   | Commands (source)            | Skills (source)                  |
|---------|------------------------------|----------------------------------|
| Claude  | `buildcli/claude/commands/*.md` | `buildcli/claude/skills/*/SKILL.md` |
| Codex   | `buildcli/codex/commands/*.md`  | `buildcli/codex/skills/*/SKILL.md`  |
| Gemini  | `buildcli/gemini/commands/*.md` | `buildcli/gemini/skills/*/SKILL.md` |
| Copilot | `buildcli/copilot/commands/*.md`| `buildcli/copilot/skills/*/SKILL.md` → installs to `.github/skills/` |

## How it holds together

1. Bootstrap copies (or symlinks) the source files into the native folders at the project root.
2. Each runtime scans only its own folder.
3. Skills always live at `skills/<name>/SKILL.md`.
4. Claude and Gemini command files are invoked by filename: `survey.md` → `/survey`. Codex pipeline command files are generated into skills: `survey.md` → `$survey`.
5. The autoload block in each startup file tells the agent the pipeline order, the band rules, and where the shared state lives. Re-running bootstrap rewrites the block in place and leaves everything around it alone.

## Agent strengths

| Agent   | Strength                        | Best stage                              |
|---------|---------------------------------|-----------------------------------------|
| Claude  | Broad reasoning, orchestration  | shape, worklist, build, rig             |
| Codex   | Focused code generation, hooks  | build, patch, rig                       |
| Gemini  | Requirements and gap analysis   | brief, audit                            |
| Copilot | In-editor, model-agnostic       | build and patch inside the IDE          |

## Notes

- `.buildcli/` is agent-neutral. Every runtime reads and writes the same state there.
- Skills load per task. No agent loads all of them at once — that would defeat the point.
- Re-run bootstrap after adding a skill, to propagate it into linked projects.
