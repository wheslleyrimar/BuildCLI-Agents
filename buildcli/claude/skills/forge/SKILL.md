---
name: forge
description: Create or refresh a project-specific skill built from this repository's real patterns. Saves to .claude/skills/<name>/SKILL.md.
---

# Forge

## Arguments

Skill name, optionally followed by a band (service|interface|store|verify|delivery|custom). Example: "payments service" or "shadcn-ui interface".

## Output

.claude/skills/<name>/SKILL.md.

## Goal

Write a `SKILL.md` that captures what is true about *this* codebase and nothing that a competent
engineer already knows. The test: an agent should be able to act on it without reopening the full
project context.

## Steps

1. Parse the skill name and band from the arguments.
   - Examples: `payments service`, `shadcn-ui interface`, `auth-flow service`, `checkout-e2e verify`
   - Band omitted → infer it from the name, or ask.
2. Check whether `.claude/skills/<name>/SKILL.md` already exists:
   - **Exists** → read it, compare against the current context, refresh whatever went stale.
   - **New** → start from the structure in `_shared/templates/skill-template.md`.
3. Load the band: `.buildcli/runtime/bcx band <band>`.
4. Open two or three representative source files in that band and extract the patterns that are
   actually in use: naming, error handling, auth guards, test layout, module boundaries.
5. Write the skill:
   - **Purpose** — one sentence, tied to how this project uses the band
   - **When to use** — 3 to 5 concrete triggers, none of them generic
   - **Context loading** — the exact band to read
   - **Workflow** — steps that name real paths, modules, and patterns from step 4
   - **Constraints** — drawn from the engineering standards and the band
   - **Example** — one input/output pair that could plausibly come from this codebase
6. Save to `.claude/skills/<name>/SKILL.md`.
7. If the skill is not already listed in `CLAUDE.md`, add it.

## Output

- Path written
- The project-specific patterns the skill now encodes
- Anything left as `NEEDS CLARIFICATION` for want of evidence

## Rules

- Every line must be specific to this project. Delete any sentence that would survive a copy-paste into another repo.
- `[band:<band>]` empty or full of `NEEDS CLARIFICATION` → run `survey` first and say so.
- Keep it under roughly 400 words.
- One concern per skill. Never fold two bands into one file.
- Skills outside the five standard bands are fine — just name them unambiguously.
