---
name: store
description: Data layer work — schemas, migrations, models, queries, caching, and validation. Reads only [band:store] from .buildcli/context.md.
---

# Skill: store

## Metadata

- Agent: Claude
- Version: 0.1.0
- Band: `[band:store]` in `.buildcli/context.md`

## Purpose

Own where the data lives: schema design, migrations, model changes, query performance, and caching.
Reads a single band to keep the context cost flat.

## When to use

- Designing or altering a database schema
- Writing or reviewing a migration
- Diagnosing a slow query
- Adding or changing an ORM model or entity
- Setting up or tuning a cache
- Reviewing data validation rules

## Context loading (minimal)

Read only:

1. The `[band:store]` block from `.buildcli/context.md`
2. The specific migration, model, or query file(s) named by the task

Do not open interface components, service logic, or the delivery band unless the task explicitly reaches into them.

## Inputs

- A task description, or the file path(s) to change
- Optional: a related brief or ERD reference

## Workflow

1. Read `[band:store]` from `.buildcli/context.md`.
2. Locate the schema, model, or query the task points at.
3. Open only the source files that matter to it.
4. Apply the change following the migration strategy and naming conventions already in use.
5. Check data integrity end to end: constraints, indexes, nullability, defaults.
6. Flag anything that breaks a caller — service models, API contracts, seed data.
7. Report back: what changed, the migration steps, and how to roll back.

## Output

- The schema, migration, or model change
- The list of files touched
- Rollback instructions when the change is destructive
- Flags for upstream impact: service models, API contracts, seed data

## Constraints

- Never drop a column or a table without explicit confirmation from the user.
- Follow the migration strategy recorded in `[band:store]`.
- Migrations stay reversible unless the brief documents the destruction as intentional.
