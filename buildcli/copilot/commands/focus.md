---
description: Move the active blueprint pointer, or list what is available.
arguments: Optional blueprint slug or path
output: Updated .buildcli/active + confirmation
usage: Paste this prompt into Copilot Chat
---

## Prompt

Switch the active blueprint, or show me the ones available.

No slug given — list mode:
1. Scan `blueprints/features/` and `blueprints/defects/` for directories holding a `brief.md`.
2. For each, show which of brief / shape / worklist / audit exist.
3. Mark the active one (from `.buildcli/active`) with `←`.

Slug given — switch mode:
1. Resolve against `blueprints/features/<slug>/`, then `blueprints/defects/<slug>/`. A path with a `features/` or `defects/` prefix is used directly.
2. Confirm `brief.md` exists there.
3. Run `buildcli active <path>` — it validates and writes the pointer.
4. Print the blueprint name, its stage, and the next step.

Rules:
- Never create or delete a blueprint. The only write is `.buildcli/active`.
- Slug present in both features and defects → ask which.
