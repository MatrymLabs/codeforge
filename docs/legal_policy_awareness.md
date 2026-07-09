# Legal & Policy Awareness

> **This is a compliance-awareness engineering note, not legal advice. Human review
> is required before relying on it.**

CodeForge provides **compliance-awareness support** — source tracking, engineering
checklists, and evidence organization. It does **not** provide legal advice and does
**not** replace qualified legal, compliance, financial, HR, safety, or
government-contracting review.

The goal is not to automate lawyering. **The goal is to prevent blind coding** —
to know *when* expert review is required and to keep the sources traceable.

## The boundary (hard rule)

**Never claim** — legally compliant · guaranteed compliant · approved by law ·
certified · safe for government use · safe for finance use · OSHA compliant ·
CMMC compliant · audit ready — *unless qualified review and evidence support that
exact claim.*

**Use instead** — compliance-aware · legal-review required · source-tracked ·
policy-mapped · audit-supporting · evidence-friendly · review-ready · human approval
required · freshness unknown · jurisdiction unknown · applicability unknown.

This mirrors the code: the Safety+QA layer reports **readiness, never compliance**
(`qa gate`, `safety review`), and the federal rules in the operating contract forbid
certification claims.

## The five anchors

| Term | Meaning |
|------|---------|
| **LawSource** | an official or authoritative source (statute, regulation, guidance, policy) |
| **PolicyMap** | how a source *may* affect a CodeForge feature — a possibility, not a ruling |
| **ComplianceCheck** | an engineering checklist, **not** a legal conclusion |
| **HumanReview** | required before relying on any legal interpretation |
| **EvidenceLedger** | proof of what source was used, when, and why |

## Jurisdiction: unknown by default

CodeForge does not guess jurisdiction. Unless a project explicitly records one, treat
it as **`jurisdiction_unknown`** and require review. The default profile:

- country: United States · state/county/city: *unconfirmed*
- deployment: *local development / demo* unless stated otherwise
- commercial use, user population, sensitive-data handling: *unconfirmed*

## What already exists (don't rebuild it)

Much of the "law/policy registry" is already built and tracked:

- **Source registry** — `federal-guidance-library` tracks federal sources to
  jurisdiction, issuing body, publication/retrieved date, version, freshness, owner,
  and related controls. (A private companion repo; codeforge reads it read-only via
  `FGL_HOME`.)
- **Freshness discipline** — `library verify <id>` confirms a stored publication date
  against its source; `regs <id>` surfaces dates; freshness is *never assumed*.
- **In-MUD lens** — `law` / `law <id>` render those sources through the
  compliance-awareness boundary (jurisdiction · freshness · **"No legal conclusion.
  Human review required."**).
- **Readiness gates** — `qa gate` / `safety review` grade features for readiness, not
  compliance.

## Feature review template (use when a feature touches a sensitive domain)

Sensitive domains: money/finance · contracts · records/retention · education ·
safety · government · children · health · employment · identity · sensitive/personal
data. When a feature touches one, record:

```
Legal/Policy Awareness Review
  Feature:                <name>
  What it does:           -
  Data involved:          -
  Jurisdiction profile:   jurisdiction_unknown unless recorded
  Possible domains:       -
  Sources checked:        -           Sources missing: -
  Freshness status:       -
  Risk level:             low / medium / high / critical
  Human review required:  yes/no
  Compliance claim allowed: no (unless qualified review + evidence)
  Safe wording:           compliance-aware / review-required / ...
  Engineering controls:   e.g. store source, record dates, audit log, approval gate,
                          sample data only, no legal conclusions in AI output
  Next action:            -
```

## AI behavior (in force)

When touching legal / regulatory / finance / safety / privacy / government /
compliance topics: do **not** give legal advice or conclusions; do **not** guess
applicability or claim compliance; prefer official sources; track publication +
retrieved dates and freshness; name assumptions and unknowns; separate source text
from AI summary; recommend human review; preserve evidence. When in doubt, say:
*"This is a compliance-awareness engineering note, not legal advice. Human review is
required before relying on it."*

## Not yet built (tracked backlog — do not imply these exist)

`ApplicabilityMapper`, `ComplianceDesignGate` as standalone code, a per-domain
`JurisdictionProfile` store, and `law check`/update-logging are **planned**, not
present. Building the source-tracking + boundary skeleton first is deliberate.
