---
name: pulse
description: Read-only pipeline snapshot — active blueprint, stage, unit counts, quality gates, next step. Writes nothing.
---

# Pulse

## Arguments

None.

## Output

Inline report. No files written.

## Goal

Answer "where am I?" in one screen. Nothing is written; this is a diagnostic.

## Steps

1. Read `.buildcli/active`. Missing → report "No active blueprint. Run `brief` to start." and stop.
2. Open the blueprint directory and load whichever files are there:
   - `brief.md` → name, kind, confidence, blocking questions
   - `shape.md` → phases, risks
   - `worklist.md` → units with bands and checks
   - `audit.md` → last verdict, if one exists
3. Infer the stage:
   - brief only → **brief**
   - brief + shape → **shape**
   - brief + shape + worklist → **worklist** (ready for `build`)
   - worklist exists and some units have landed → **build**
   - `audit.md` exists → **audit**
4. Count unit states from `worklist.md`, reading whatever done/blocked markers `build` left behind.
5. If `.buildcli/journal/session.log` exists, pull the last 5 entries.
6. Render the report.

## Output format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Blueprint : blueprints/features/checkout-flow
 Kind      : feature
 Stage     : build  ←  here
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Pipeline  : survey ✓ → brief ✓ → shape ✓ → worklist ✓ → [build] → audit
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Units     : 8 total
             ✅ 5 done         (service ×3, store ×2)
             🔄 2 in progress  (interface ×2)
             ❌ 1 blocked      — W06: waiting on W04
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Quality gates
             ✅ API contract matches the brief
             ⚠️  Coverage below 80% (74%)
             ❌ E2E scenario not written
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Last audit : none yet  →  run /audit
 Confidence : high
 Blocking   : none
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Recent activity (.buildcli/journal)
   14:32 EDIT src/api/checkout.ts
   14:33 EDIT src/api/checkout.test.ts
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Next step: /build   (2 units remaining)
            or /audit to validate what landed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Rules

- Read-only. Never write, never modify, never create.
- A missing pipeline file means "stage not started", not an error.
- The activity section is optional — skip it silently when the journal is absent.
- Always close with a concrete next step.
