---
name: Feature request
about: Propose a new capability, scoped to the smallest useful slice
title: "feat: "
labels: ["enhancement"]
---

## The need

What problem does this solve, and for whom (player, owner/wizard, interviewer, contributor)?

## Smallest useful slice

The minimum version that proves the idea. Resist speculative scope; the store stocks finished
parts, not intentions.

## How it fits CodeForge

- Which discipline/system does it extend (engine, registry, QA/safety, PM, docs, web)?
- Does it touch a persisted identifier (label, seed key, DB column, CLI verb)? If so, note it.
- Any new dependency? If yes, it must answer the Dependency Approval Rule (`docs/tooling_strategy.md`).

## Evidence of done

- Test twin (acceptance + refusal cases):
- Docs impact:
- How it will be verified (`make check` + the relevant gate):

## Alternatives considered (optional)

Including the frameless/stdlib option that was weighed.
