---
name: focus
description: Move the active blueprint pointer without re-running brief. Lists blueprints or switches to one. Updates .prism/active.
---

# Focus

## Arguments

(optional) Blueprint slug or path. Omitted → lists everything available.

## Output

Updated .buildcli/active + confirmation.

## Goal

Change which blueprint is live — for juggling features in parallel, or picking back up something
started last week.

## Steps

### No arguments — list mode

1. Scan `blueprints/features/` and `blueprints/defects/` for directories containing a `brief.md`.
2. Read each one's header comments for name, kind, created date.
3. Mark the currently active blueprint (from `.buildcli/active`) with `←`.
4. Show per-blueprint progress: which of brief / shape / worklist / audit exist.
5. Invite the user to pass a slug to switch.

### With an argument — switch mode

1. Resolve the target:
   - Bare slug → check `blueprints/features/<slug>/`, then `blueprints/defects/<slug>/`.
   - Argument already carries a `features/` or `defects/` prefix → use it directly.
   - Nothing matches → list what exists and ask again.
2. Confirm `brief.md` is present in the target directory.
3. Run `bcx active <path>` — it validates and writes the pointer.
4. Read the blueprint's name and stage; confirm the move.

## Output — list mode

```
Blueprints:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 features/
   checkout-flow   [brief ✓ shape ✓ worklist ✓ audit –]  ← active
   user-auth       [brief ✓ shape ✓ worklist – audit –]
   dashboard-v2    [brief ✓ shape – worklist – audit –]

 defects/
   payment-safari  [brief ✓ shape – worklist – audit –]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Run: /focus user-auth
```

## Output — switch mode

```
Active blueprint moved:
  from: blueprints/features/checkout-flow
  to:   blueprints/features/user-auth

Stage: shape  (worklist not generated yet)
Next step: /worklist
```

## Rules

- Never create or delete a blueprint. The only file this command writes is `.buildcli/active`.
- Slug present under both `features/` and `defects/` → ask which one.
- Always print the stage after switching, so the user knows where to resume.
