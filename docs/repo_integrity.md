# Repo Integrity Ritual

*One honest command for repo health — evidence and warnings, not a certificate.*

Run it:

```bash
make repo-integrity      # python -m parts.integrity
```

It composes the checks CodeForge already owns into one dated report under
`reports/repo_integrity/` (git-ignored generated evidence), covering: code quality,
security, license/source origin, originality awareness, professional presentation,
and a truth/VeritasGate pass.

## What it can and cannot prove

**Repo cleanliness is not one scan.** CodeForge repo integrity requires all of:

1. code quality checks · 2. security checks · 3. dependency checks · 4. secret scans ·
5. license/source scans · 6. documentation review · 7. truth review · 8. **human judgment.**

> Similarity is a signal. License metadata is evidence. Tests prove behavior.
> Documentation proves intent. VeritasGate keeps the claims honest.

Hard boundaries (integrity-first):

- **It does not prove legal originality, security, or compliance.** It organizes
  evidence and flags review needs.
- **It never uploads your code** to any third-party plagiarism/similarity service.
- **A missing tool is reported `not_configured`**, never silently passed or faked.
- **It detects tools** (ruff, mypy, pytest, bandit, pip-audit) and points at
  `make check` / `make security` for the live run — it does not re-run the suite.

## How it composes (nothing rebuilt)

| Report section | Source (already in the repo) |
|----------------|------------------------------|
| Code quality | tool detection → `make check` (ruff · mypy · pytest · property) |
| Security | `make security` (bandit + pip-audit + **`make secrets`** detect-secrets) |
| License / source origin | the hardware catalog's `source_status` / `license` / `influence` |
| Originality awareness | catalog provenance; states the "not universal originality" limit |
| Presentation | presence of README · LICENSE · CHANGELOG · SECURITY · CONTRIBUTING · docs |
| Truth / VeritasGate | registry `validate()` · `qa gate` readiness · README overclaim scan |

## The gap it surfaced — now closed

The report's first run flagged **secret scanning as `not_configured`** (top next
action). That gap is now closed: `make secrets` runs **detect-secrets** against an
audited `.secrets.baseline`, failing on any tracked secret not already in the baseline
(verified: it passes clean and catches a planted key). It's folded into `make security`
and gates in CI. The report now shows `secret scan: detected` — the tool flagged its
own gap, and closing it fixed the tool's own output. That self-correcting loop is the
point of integrity-first.

Regenerate the baseline after auditing new findings:
`detect-secrets scan --exclude-files '\.venv/' > .secrets.baseline`.
