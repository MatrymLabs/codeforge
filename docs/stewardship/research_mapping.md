# Research mapping: Fraud, Waste & Abuse reduction -> CodeForge (the Stewardship Gate)

*How the report "Fraud, Waste, and Abuse Reduction for Software Engineering and AI-Assisted
Delivery" translates into CodeForge controls. The report's own bottom line: do not solve FWA
with one big "security AI" -- build a layered assurance system. Doctrine: make changes
traceable, permissions narrow, AI output provisional, policies executable, risk visible,
high-impact changes review-heavy, failures reusable, controls measurable -- without taxing
low-risk work (alert fatigue is itself waste).*

## Evidence labels (the report's own honesty, carried here)

The report separates **venue-verified/peer-reviewed** work from **highly relevant but
preprint** work, and says the distinction matters for roadmap confidence. So do we:

- **Venue-verified** - a journal or workshop-associated paper exposed a venue.
- **Preprint** - strong relevance, but no peer-reviewed venue exposed in accessible sources.

## The three failure modes and their counters

| Mode | Means | Primary counter | CodeForge translation |
|---|---|---|---|
| **Fraud** | unverifiable artifacts, forged build/test evidence, malicious deps, misleading AI changes | provenance + verifiability | ProvenanceGate (SBOM/attestation), DependencyGate (admission), AI-disclosure |
| **Abuse** | overprivileged automation, policy bypass, unsafe tool use, prompt injection, credential misuse | shrink authority + separate duties | least-privilege workflows, PolicyGate, rank-gate, prompt-injection red-team |
| **Waste** | needless compute, pipeline churn, false positives, duplicate effort, AI bloat | selective attention + evidence-driven triage | RiskRouter (don't tax low-risk), CounterexampleBank (no repeat rediscovery), WorkflowLinter |

## Control mapping (what exists vs the gap this subsystem fills)

| Report control | Label | Already in CodeForge | Gap the Stewardship Gate fills |
|---|---|---|---|
| Provenance / SBOM / attestation | Preprint (SoK, OmniBOR) | `make sbom`, dated+hashed evidence bundles, RepoIntegrityRitual | verify attestation before merge (ProvenanceGate, later slice) |
| Least-privilege CI/runtime | Preprint (Granite) | workflow `permissions:` declared, rank-gate, FailsafeRunner allowlist | permission-budget linter (WorkflowLinter, later) |
| Executable policy (merge/deploy/tool-use) | Preprint (P2P/Rego) | VeritasGate, QualityGate, SafetyReview, KeelGate | **PolicyGate: one visible merge-eligibility verdict (this slice)** |
| Risk-weighted human review | Preprint (agentic-PR study) | PR Risk field, critical-junction rule | **RiskRouter: score by touched surface -> review depth (this slice)** |
| Dependency admission (anti-hallucination) | Preprint (Spracklen) | `dependency_ledger.toml` + `make deps`, `make audit` (pip-audit) | per-package existence/CVE/license admission (DependencyGate, later) |
| Secure AI code review | Venue + preprint (SLR; Fu; Yu; Tony) | evaluator swarm (no merge authority), architect AI (mockable) | narrow-context CWE-framed reviewer (later) |
| Warning-guided repair | Preprint (DeepCode AI Fix) | `make patch` (scan -> fix -> re-verify) | bounded repair loop with human sign-off (later) |
| Reusable failures | Preprint (adjacent) | **CounterexampleBank already built** (`parts/evolution/counterexamples.py`) | reuse for blocked packages / failed prompts |
| Red-team the assistant | Venue (garak); preprint (CyberSecEval2) | - | garak/CyberSecEval-style probe suite (later) |
| Traceability spine | Preprint (workflow-cost studies) | Conventional Commits, branch->PR->CI, classification registry | append-only AuditLedger (later) |

## This slice (v1): the executable core

`parts/stewardship/`: a typed **ChangeDescriptor** (the assurance facts of a change, read not
re-scanned), a **RiskRouter** (`assess_risk`: score 0-100 from visible factors -> low/medium/high
tier -> 0/1/2 required approvals), and the **StewardshipGate** (`verify_change`): hard gates first
(tests pass, no blocking SAST, no secrets, dependencies admitted, AI involvement disclosed), then
risk-routed human approval. Every check is visible; nothing auto-merges (it advises; a human and
CI branch protection decide). This is the report's `verify_change` gate (p9), adapted to what
CodeForge can verify today.

## Lean, not bureaucratic (the report's headline risk)

Alert fatigue makes more gates into more waste. So the gate **composes existing signals** (it
reads `make check` / `security` / `deps` outcomes; it never re-scans), and **low-risk work pays
nothing** (0 extra approvals). Oversight tracks risk, never "looks simple."

## Metrics (FWA-distinguishing, per the report)

- **Fraud:** unsigned-artifact rate, unverifiable-build rate, AI-authorship disclosure
  completeness, package-hallucination block rate.
- **Abuse:** overprivileged-workflow-step rate, policy-violation rate, secret-exposure incidents,
  prompt-injection success rate.
- **Waste:** CI rerun minutes, false-positive rate, review minutes per accepted PR, token cost
  per accepted AI-authored change.

## References (APA 7)

Bhatt, M., et al. (2024). *CyberSecEval 2: A wide-ranging cybersecurity evaluation suite for
large language models* [Preprint]. arXiv.

Berabi, B., Gronskiy, A., Raychev, V., Sivanrupan, G., Chibotaru, V., & Vechev, M. (2024).
*DeepCode AI Fix: Fixing security vulnerabilities with large language models* [Preprint]. arXiv.

Derczynski, L., Galinkin, E., Martin, J., Majumdar, S., & Inie, N. (2024). *garak: A framework
for security probing large language models* [IEEE/ACM RAIE workshop-associated]. arXiv.

Fu, Y., Liang, P., Tahir, A., Li, Z., Shahin, M., Yu, J., & Chen, J. (2023). *Security weaknesses
of Copilot-generated code in GitHub projects: An empirical study* [Preprint]. arXiv.

Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). *Not what
you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt
injection* [ACM AISec workshop-associated]. arXiv.

Husein, R. A., Aburajouh, H., & Catal, C. (2025). *Large language models for code completion: A
systematic literature review*. Computer Standards & Interfaces.

Moazen, M., Ahmadian, A. M., & Balliu, M. (2025). *Granite: Granular runtime enforcement for
GitHub Actions permissions* [Preprint]. arXiv.

Okafor, C., Schorlemmer, T. R., Torres-Arias, S., & Davis, J. C. (2024). *SoK: Analysis of
software supply chain security by establishing secure design properties* [Preprint]. arXiv.

Seshadri, B., Han, Y., Olson, C., Pollak, D., & Tomasevic, V. (2024). *OmniBOR: A system for
automatic, verifiable artifact resolution across software supply chains* [Preprint]. arXiv.

Siddiq, M. L., et al. (2026). *Security in the age of AI teammates: An empirical study of agentic
pull requests on GitHub* [Preprint]. arXiv.

Spracklen, J., et al. (2024). *We have a package for you! A comprehensive analysis of package
hallucinations by code generating LLMs* [Preprint]. arXiv.

Tony, C., Diaz Ferreyra, N. E., Mutas, M., Dhiff, S., & Scandariato, R. (2024). *Prompting
techniques for secure code generation: A systematic investigation* [Preprint]. arXiv.

Valenzuela-Toledo, P., Bergel, A., Kehrer, T., & Nierstrasz, O. (2024). *The hidden costs of
automation: An empirical study on GitHub Actions workflow maintenance* [Preprint]. arXiv.

Xu, W., et al. (2025). *A two-staged LLM-based framework for CI/CD failure detection and
remediation with industrial validation* [Preprint]. arXiv.

Yu, J., Liang, P., Fu, Y., Tahir, A., Shahin, M., Wang, C., & Cai, Y. (2024). *An insight into
security code review with LLMs: Capabilities, obstacles and influential factors* [Preprint]. arXiv.
