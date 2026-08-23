---
name: store
description: Analyze, review, and specify schema design, migrations, model changes, query performance, and caching. Reads only [band:store] from .buildcli/context.md.
---

# Skill: store

## Metadata

- Agent: Gemini
- Version: 0.1.0
- Band: `[band:store]` in `.buildcli/context.md`

## Purpose

Reason about the data layer — schema design, migrations, model changes, query performance, and caching — and surface the gaps, risks, and ambiguities before code is written.
Reads a single band so the context cost stays flat as the project grows.

## When to use

- Designing or altering a database schema
- Writing or reviewing a migration
- Diagnosing a slow query
- Adding or changing an ORM model or entity
- Setting up or tuning a cache
- Reviewing data validation rules

## Context loading (minimal)

Read only:

1. The `[band:store]` block, via the runtime:
   ```bash
   buildcli band store
   ```
   Do not open `.buildcli/context.md` directly — with the harness enforced, that read is blocked
2. The specific migration, model, or query file(s) named by the task

Do not open interface components, service logic, or the delivery band unless the task explicitly reaches into them.

## Inputs

- A task description, or the file path(s) in scope
- Optional: the active blueprint's `worklist.md` entry for the current unit

## Workflow

1. Run `buildcli band store` to load the band. Nothing else from the context file.
2. Locate the schema, model, or query the task points at.
3. Open only the source files that matter to it.
4. Make the smallest change that satisfies the task and matches the conventions already in the band.
5. Check data integrity end to end: constraints, indexes, nullability, defaults.
6. Name the risks and the assumptions the change forces.
7. Report back: findings, recommended approach, and open questions.

## Output

- Analysis or review notes
- The list of files examined
- Risks and open questions
- Flags for downstream impact: service models, API contracts, seed data

## Constraints

- Never drop a column or a table without explicit confirmation from the user.
- Follow the migration strategy recorded in `[band:store]`.
- Migrations stay reversible unless the brief documents the destruction as intentional.
