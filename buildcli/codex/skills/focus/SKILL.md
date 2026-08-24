---
name: focus
description: Move the active blueprint pointer. Lists blueprints, or switches to one by slug.
---

# Focus

## Arguments

(optional) Blueprint slug or path. Omitted → lists everything.

## Output

Updated .buildcli/active + confirmation.
## Steps

### No arguments — list mode

1. Scan `blueprints/features/` and `blueprints/defects/` for directories holding a `brief.md`.
2. For each, show which of brief / shape / worklist / audit exist.
3. Mark the active one (from `.buildcli/active`) with `←`.

### With an argument — switch mode

1. Resolve the slug against `blueprints/features/<slug>/`, then `blueprints/defects/<slug>/`.
   A path with a `features/` or `defects/` prefix is used directly. No match → list and ask again.
2. Confirm `brief.md` exists there.
3. Run `.buildcli/runtime/bcx active <path>` — it validates and writes the pointer.
4. Print the blueprint name, its stage, and the next step.

## Rules

- Never create or delete a blueprint. The only write is `.buildcli/active`.
- Slug present in both features and defects → ask which.
- Always print the stage after switching.
