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
| Security | `make security` (bandit + pip-audit); **secret scan: not_configured** (gap) |
| License / source origin | the hardware catalog's `source_status` / `license` / `influence` |
| Originality awareness | catalog provenance; states the "not universal originality" limit |
| Presentation | presence of README · LICENSE · CHANGELOG · SECURITY · CONTRIBUTING · docs |
| Truth / VeritasGate | registry `validate()` · `qa gate` readiness · README overclaim scan |

## Known gap it surfaces (honestly)

**Secret scanning is `not_configured`.** codeforge has `make security` (bandit +
pip-audit) but no `make secrets` (detect-secrets, baselined) yet — the other ship
repos carry it. The integrity report recommends adding it as the top next action
rather than pretending secrets were scanned. That honesty is the point of the tool.
