---
name: <skill-name>
description: <one line — what this skill does and which band it reads>
---

# Skill: <name>

## Metadata

- Agent: <Claude|Codex|Gemini|Copilot|Any>
- Version: 0.1.0
- Band: `[band:<name>]` in `context.md`

## Purpose

One sentence describing the problem this skill owns.

## When to use

- Trigger 1
- Trigger 2

## Context loading (minimal)

Before starting, read only:
1. The `[band:<name>]` block from `.buildcli/context.md`
2. The specific file(s) named by the task

Do NOT load other bands unless the task explicitly spans them.

## Inputs

- Required inputs
- Optional inputs

## Workflow

1. Step one
2. Step two
3. Step three

## Output

- Expected artifact(s)
- Output format

## Constraints

- Technical constraints
- Security / compliance constraints
