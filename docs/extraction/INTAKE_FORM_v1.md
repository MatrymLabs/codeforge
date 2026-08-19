# INTAKE FORM v1 (DRAFT, derived)

**Not doctrine.** A draft extracted on 2026-08-19 from the only two products this factory has
actually produced and proven: DONE-1 (M2 Engine Real) and DONE-2 (RF-001). Every field below
exists because a proof stage would have been unaskable without it. Nothing here is speculative,
and that restraint is the point: a schema built before the build that consumes it violates the
pull rule, so this was built after two builds and derived from what they needed.

**Consume-first, logged.** Certified Tier (`hardware-store/catalog/`, 22 Parts) and the Working
Shelf (`codeforge/catalog/parts.yaml`) were both searched for an intake, form, questionnaire or
schema Part. Zero capabilities match. The apparent hits were the word INTAKE inside a
`source_studied` provenance field, which is an R&D research intake and a different thing entirely.
Both tiers searched, nothing applicable, nothing consumed.

---

## The ten fields

| # | field | what it decides | which done demanded it |
|---|---|---|---|
| 1 | `plain_request` | what a human actually asked for, in their words | both |
| 2 | `expected_output` | the artifact handed back: a bootable directory, a rendered grid, a file | both, and they differ |
| 3 | `target_user` | who runs it, which decides the surface | both |
| 4 | `product_category` | engine pour, tool, service, game | both, and they differ |
| 5 | `languages` | required, allowed, forbidden | DONE-2 (Python core, Kotlin surface) |
| 6 | `accepts_untrusted_input` | whether hostile-input fixtures are mandatory | **DONE-2** |
| 7 | `persists_state` | whether persist/restart/survive stages exist at all | **DONE-1** |
| 8 | `must_run_detached` | whether an isolation stage is required | **DONE-1** |
| 9 | `input_provenance_constraints` | legal limits on what may be read or committed | **DONE-2** |
| 10 | `acceptance_proof` | the command whose output means done | both |

## The test the launch demanded: could BOTH dones have been requested with these ten alone?

**DONE-1, expressed in the ten:**

```yaml
plain_request:      "a standalone MUD I can run without the engine repo present"
expected_output:    a directory that boots and serves play commands
target_user:        an operator running the poured product
product_category:   engine pour -> standalone game
languages:          {required: [python]}
accepts_untrusted_input: false
persists_state:     true          # -> demands persist, restart, survive stages
must_run_detached:  true          # -> demands the isolation stage
input_provenance_constraints: none
acceptance_proof:   "state written, interpreter restarted, state read back identical"
```

**DONE-2, expressed in the ten:**

```yaml
plain_request:      "show me the tiles inside a cartridge image"
expected_output:    an ASCII tile grid plus a traceable extraction manifest
target_user:        a developer inspecting a ROM
product_category:   tool
languages:          {required: [python], allowed: [kotlin]}
accepts_untrusted_input: true     # -> demands truncated/garbage/oversized fixtures
persists_state:     false         # -> NO persist stage. Correctly absent, not skipped
must_run_detached:  false
input_provenance_constraints: "owned, homebrew or synthetic only; never a commercial dump"
acceptance_proof:   "tiles decode AND source bytes are unchanged, hashed before and after"
```

**Verdict: PASS.** Both were expressible without inventing a field, and more usefully, fields 6
through 9 answer DIFFERENTLY for the two products. A field that reads the same for every product
is not a field, it is a constant, and it belongs in the standard rather than the form.

## What field 7 buys, stated plainly

`persists_state: false` on DONE-2 is why RF-001 has no persist stage. That is the difference
between a control that is **NOT_APPLICABLE with a recorded reason** and a control that was
silently skipped. The Universal Clause names that distinction as the whole legitimate variation,
and this field is where it gets resolved from a fact rather than assumed.

## What this form deliberately does NOT ask

- Legal determinations. Field 9 asks what the input IS, not whether the requester is subject to a
  statute. A requester who must know the law to fill in a form will guess.
- Compliance booleans. Nothing here says `hipaa: true`. Applicability is resolved at CONFIGURE
  from facts, and no fact either done produced would have triggered an overlay.
- Anything the two dones did not use. Deployment model, payment data, CUI and personal data are
  all real questions and none of them were asked by either product, so none are here. They join
  when an intake produces a fact that needs them.

## Known limitation

**Two products is a thin basis, and both were built by the factory that is now describing itself.**
Neither was requested by an outside person. Field 1 has never been filled in by someone who did not
already know the answer, which is exactly the condition this form exists to survive. The first
outside request is the real test, and this draft should be expected to move when it arrives.
