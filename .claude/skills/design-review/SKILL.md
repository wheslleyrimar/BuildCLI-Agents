---
name: design-review
description: Weigh an architecture decision for scalability, reliability, security, and maintainability before anything gets built.
---

# Design Review

## When to use

Reach for this before implementation, when the decision is expensive to reverse: choosing between
two architectures, accepting a tradeoff, or deciding whether a risk is worth carrying.

## Context loading (minimal)

Read only:

1. The Architecture and Engineering Standards blocks from `.buildcli/context.md`
2. The bands the decision actually touches
3. `shape.md` from the active blueprint, if one exists

## Workflow

1. State the decision in one sentence, and what happens if it is wrong.
2. Lay out the viable options — at least two — with their real tradeoffs, not their marketing.
3. Rank the top risks and pair each with a mitigation someone could actually execute.
4. Define the acceptance checks that would prove the decision was right.
5. Recommend one option and say plainly why the others lose.

## Output

- A review memo: decision, options, recommendation
- A risk matrix: risk, likelihood, impact, mitigation
- Acceptance checks that make the decision falsifiable

## Constraints

- No recommendation without a stated tradeoff. Every choice costs something.
- Ground the review in the recorded context, not in generic best practice.
- If the evidence does not support a call, say so and name what would settle it.
