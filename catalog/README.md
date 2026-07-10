# The Hardware Catalog

CodeForge builds code parts for a game - and the good ones do a second job in the
real world. This catalog is the "hardware store" counter: it records, for each
part worth reusing, **where the same code serves outside the game** (government,
finance, compliance, records, general software).

Two catalogs, two depths:

| Command | What it shows |
|---------|---------------|
| `make store` | Auto-generated inventory of *every* engine part, from its `CARD:` line. |
| `make hardware` | This curated catalog - the parts documented for **cross-domain reuse**. |

The data lives in [`parts.yaml`](parts.yaml); the loader/validator is
`parts/hardware.py` (a bad row fails loud - it is never stocked). Override the
path with `CODEFORGE_CATALOG`.

## Entry schema

```yaml
- id: rank-gate            # required · stable, lowercase-kebab, unique
  name: Rank Gate          # required · human name
  source: parts/ranks.py   # required · the file that implements it
  category: authorization  # required · one word (authorization, messaging, …)
  maturity: shipped        # required · prototype | beta | shipped
  risk: low                # required · low | medium | high
  source_status: original  # optional (default original) · original | mit | apache-2.0 | ...
  license: MIT             # optional (default MIT) · this repo's own code is MIT
  influence: "…"           # optional · the KNOWN PATTERN it was rebuilt from
  reuse:                   # required · non-empty map of domain -> concrete use
    game: "…"
    government: "…"
    finance: "…"
    compliance: "…"
    general: "…"
  purpose: >               # required · one honest sentence: what it does
    …
  tags: [rbac, security]   # optional
  reuse_score: 5           # optional · 1–5, how broadly it reuses
```

## Rules

- **Honest reuse only.** A domain line means the *same code* genuinely serves that
  job - not a maybe. If it doesn't fit, leave the domain out.
- **`source` points at real code.** The catalog documents parts that exist and are
  tested; it is not a wishlist.
- **`maturity` is earned:** `shipped` means shipped + tested on `main`.
- **Two maturity vocabularies, on purpose - different axes.** This catalog's
  `maturity` (`prototype | beta | shipped`) rates **reuse-readiness** - how ready a
  part is to be *lifted into another project*. The Classification Registry's `status`
  (`prototype | active | hardened | deprecated | archived | superseded`) tracks an
  object's **lifecycle** - where it is between conception and retirement. They're
  orthogonal: a part can be `active` in the engine (registry) *and* `shipped` for reuse
  (catalog). Don't collapse them.
- **Free-to-use only (the provenance rule).** Only stock a part whose license is
  clearly free to use. Don't harvest code - harvest *patterns* and rebuild them as
  original CodeForge parts. `source_status` records the provenance; an unclear license
  means the part is not stocked in the first place (the loader refuses any status
  outside the free-to-use set). Every part here is `original` - this repo's own MIT code.
- **Harvest patterns, not code (proven, not asserted).** `influence` records the *known
  pattern* a part was rebuilt from (RBAC, pub/sub, allowlist-without-a-shell). The part
  is an original implementation *of the pattern* - the concept is reused, the expression
  is ours.
- **Add a part when it proves reusable**, not before - the store stocks finished
  parts, not intentions.

## Roadmap for this catalog

Today it's a validated data file + a viewer (`make hardware`). Next steps (see
[`../docs/holodeck/ROADMAP.md`](../docs/holodeck/ROADMAP.md)): expose it in-world as
the `catalog`/`parts`/`hardware` Workshop commands, add search by tag/domain, and
let the Architect NPC suggest an existing part before you build a new one.
