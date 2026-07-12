# CodeForge - the Proving Ground & the Hardware Store

## Vision

CodeForge is two products sharing one engine.

- **A MUD-powered engineering proving ground.** You log in as a builder, enter your
  Workshop, and engineer software *through the world* - talk to an Architect NPC
  (an AI pair-programmer), run diagnostics at a console, read test results in-world,
  and design systems interactively. The game is the proving ground.
- **A reusable-code hardware store.** Every part built for the game that proves
  generally useful is cataloged as a professional component - with its purpose,
  tests, risks, and the **real-world domains it serves** (government, finance,
  compliance, records, general software). The hardware store is the product.

> Build code once, understand it deeply, reuse it intelligently. The MUD is the
> interface; the Workshop is the cockpit; the NPC is the pair-programmer; the
> catalog is the parts library. PyCharm is where you go only for the serious
> decisions - approving a risky diff, reviewing architecture, resolving what must
> not be automated blindly.

This is not a departure from today's CodeForge - it is its next spiral. The engine,
the tick, the seed-driven world, the control-panel `make`, and `parts/store.py`
(already labeled *"the hardware store"*) are the seed of it.

## Architecture map (layers)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Reports / Evidence Layer   reports/, dated + hashed, saved not spammed │
├──────────────────────────────────────────────────────────────────────┤
│ Safety / Governance Layer  FailsafeRunner: allowlist, approvals, logs  │  ← wraps everything below
├──────────────────────────────────────────────────────────────────────┤
│ Industry Adapter Layer     tag parts into gov/finance/compliance tracks│
│ Hardware Catalog Layer     catalog/parts.yaml + parts/hardware.py  ✅  │
│ Reusable Parts Layer       parts/*.py cards (the code being cataloged) │
├──────────────────────────────────────────────────────────────────────┤
│ Code Generation Layer      PatchProposal → branch → diff → test → evid.│  (late, gated)
│ Command Console Layer      CommandRelay: safe, allowlisted runners     │
│ AI NPC Layer               ArchitectNPC: advisory first, redacted ctx  │
│ Workshop Interface Layer   the Workshop room + in-world commands       │
├──────────────────────────────────────────────────────────────────────┤
│ MUD / Game Layer           the engine tick, rooms, NPCs, combat    ✅  │
└──────────────────────────────────────────────────────────────────────┘
   ✅ = exists today · everything above the game layer is the climb
```

Read the layers top-down for *trust* (governance wraps all), bottom-up for *build
order* (the game exists; we climb through Workshop → NPC → console → catalog →
generation). **Nothing risky runs without the Safety layer around it.**

## What exists today (the foundation is real)

- **Game layer:** the engine tick (`handle_command`), seed worlds, TCP + browser
  gateways, combat, ranks, accounts, a full CI-gated test suite, a live browser demo.
- **Reusable parts:** `parts/*.py` cards, each with a `CARD:` line and a test twin.
- **Hardware store, v0:** `make store` (auto inventory) and now **`make hardware`**
  (the cross-domain catalog, `catalog/parts.yaml` + `parts/hardware.py`).
- **Ritual & control panel:** `make ritual`, `make check/doctor/patch/daily`.

## MVP - the smallest working proving ground

The first end-to-end slice we are climbing toward (not all at once):

1. `make ritual` lights the workshop and opens the MUD. *(exists)*
2. Log in as a builder. *(exists)*
3. **Enter the `workshop` room** - the engineering hub. *(done - furnished off the cellar)*
4. Run `workshop` / `catalog` / `reuse <term>` in-world to browse reusable parts. *(done)*
5. Run safe read-only `diagnostics` (tests, lint, git status) through a **safe runner**.
6. **Reports** of those runs are readable in-world and saved to `reports/`.
7. Talk to a **read-only Architect NPC** for advice.
8. The catalog stocks **at least four real parts** with domain reuse. *(done - see `make hardware`)*

Steps 1-4 and the catalog (8) are done - you can log in, walk into the Workshop,
and browse the hardware store in-world today. The MVP's remaining items are 5-7
(safe diagnostics, in-world reports, the read-only Architect NPC), climbed in the
order in [`ROADMAP.md`](ROADMAP.md), behind the guarantees in [`SAFETY.md`](SAFETY.md).

## File & folder plan (target shape)

Grown proportionally - not scaffolded empty. Today's `parts/` already holds the
game + reusable code; new subsystems land as new cards, not new top-level sprawl.

```
codeforge/
  parts/            # engine cards + reusable parts (the code being cataloged)
    hardware.py     #   ✅ the catalog loader/validator
    workshop.py     #   → Workshop commands (Phase 3)
    console.py      #   → CommandRelay, the safe runner (Phase 6)
    architect.py    #   → ArchitectNPC, the AI seam (Phase 5)
  catalog/          # ✅ the hardware store data
    parts.yaml
    README.md
  seeds/            # ✅ worlds as data - the Workshop room lives here (Phase 2)
  reports/          # → saved run outputs, by kind (Phase 7; gitignored)
  docs/proving_ground/    # ✅ this blueprint (VISION, ROADMAP, SAFETY)
  tests/            # ✅ a twin per card
```

See [`ROADMAP.md`](ROADMAP.md) for the phased staircase, definition of done per
phase, and how each phase translates into portfolio evidence.
