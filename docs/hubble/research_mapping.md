# Research mapping: Clinical workflow patterns -> CodeForge (Hubble)

*How the report "Clinical Workflow Design Patterns for CodeForge" translates into a diagnostic
layer. The clinical lesson is NOT to "act like a hospital"; it is that high-reliability clinical
systems break risky work into explicit phases, require checkpoints before irreversible action,
separate advisory output from final judgment, monitor after release, and turn every incident into
learning. The report's bottom line: build CodeForge as a clinical operating system for coding
work, and if you do one thing first, make it the diagnostic runner plus checklist gates.*

## Evidence honesty (the report's own caveat, carried here)

The evidence is strongest on **consensus governance** (FUTURE-AI), **OR simulation/teamwork**
(VORTeX, digital-twin OR), **mental-health safety** (LLMs fail high-risk crisis tasks even when
they sound supportive), and **post-deployment monitoring** (treat surveillance as hypothesis
testing). It is **weaker on direct transfer to routine software engineering**: several key papers
are pilots, qualitative studies, systematic reviews, or preprints. So these patterns are **tested
design hypotheses to validate inside CodeForge**, not universal truths -- exactly how this layer
treats them.

## The six clinical families and CodeForge's state

| Clinical family | CodeForge already has | Gap Hubble fills |
|---|---|---|
| Health checks (a "vitals panel") | `make doctor`, `inspect` (frameup), `repo-integrity`, `integrity.py` | - (reused) |
| Diagnostic runners | `qa gate`, `run <check>`, `diagnostics` (FailsafeRunner), `truth check` | **a decision core that turns findings into an action** |
| Governance registries | classification registry, Stewardship Gate, SafetyReview | - (composed) |
| Human-review escalation | Stewardship RiskRouter, critical-junction rule | **non-overridable escalation classes (this slice)** |
| Incident learning loops | postmortems, runbooks, CounterexampleBank | structured incident capture (later slice) |
| Simulation labs | - | replay lab on de-identified traces (later slice) |

## This slice (v1): differential diagnosis before intervention

`parts/hubble/diagnosis.py`: `DiagnosticFinding[]` across dimensions (static / security /
dependency / sandbox / retrieval-grounding) -> `decide()` -> a `DiagnosticDecision` with
confidence and a recommended action (`proceed` / `revise` / `escalate` / `stop`), reasons visible.

The load-bearing pattern is not the confidence formula; it is the **non-overridable escalation
class**. A failure in `security`, `sandbox`, or `retrieval_grounding` forces `escalate` regardless
of confidence -- high confidence can never buy past a security or sandbox failure. This is the
report's "consult attending" threshold, and the clinical distinction between a routine finding and
an urgent referral trigger. Defaulting to a differential (candidate failure modes + the evidence
that would confirm them) also reduces **premature closure**, a known failure mode in both
diagnosis and debugging.

## Composition (not duplication)

Hubble does not re-run scans. The findings are the OUTPUTS of CodeForge's existing surface: a
change's SAST/secret findings (the Stewardship Gate), sandbox/integration results (`qa gate`,
`smoke`), dependency admission (DependencyGate), and evidence-grounding for AI claims. The
diagnostic decision is the layer that reads them and recommends an action. Later slices add the
case-file + checklist phases, structured incident capture, and a replay lab.

## Roadmap (the report's order: workflow discipline before autonomy)

intake/triage -> **diagnostic decision (this slice)** -> checklist phases (sign-in/time-out/
sign-out) -> incident capture -> monitoring as hypothesis testing -> replay/simulation lab. Add
autonomy last, and only after piloting. Key risks the report names: ceremonial compliance,
false reassurance, over-automation under ambiguity, and data leakage during replay.

## Metrics that matter (measurement-based care)

escalation rate by case type, false-positive/false-negative diagnostic findings, post-release
rollback rate, mean time to detect / recover, incident recurrence rate, evidence-grounding
coverage for generated claims, reviewer override rate -- preferred over vanity metrics like lines
generated or acceptance rate.

## References (best-effort APA 7; several are pilots/preprints, labeled honestly)

Barker, J., Demirel, D., Jackson, C., et al. (2026). *Integrating virtual reality and large
language models for team-based non-technical skills training and evaluation in the operating room*.
npj Digital Surgery, 1, Article 10. https://doi.org/10.1038/s44484-026-00009-3

Dolin, P., Li, W., Dasarathy, G., & Berisha, V. (2025). *Statistically valid post-deployment
monitoring should be standard for AI-based digital health*. In Proceedings of NeurIPS 2025.

Gravel, J., D'Amours-Gravel, M., & Osmanlliu, E. (2023). *Learning to fake it: Limited responses
and fabricated references provided by ChatGPT for medical questions*. Mayo Clinic Proceedings:
Digital Health.

Lekadir, K., Frangi, A. F., Porras, A. R., et al. (2025). *FUTURE-AI: International consensus
guideline for trustworthy and deployable artificial intelligence in healthcare*. BMJ, 388,
e081554. https://doi.org/10.1136/bmj-2024-081554

Linguraru, M. G., Bakas, S., Aboian, M., et al. (2024). *Clinical, cultural, computational, and
regulatory considerations to deploy AI in radiology: Perspectives of RSNA and MICCAI experts*.
Radiology: Artificial Intelligence, 6(4), e240225. https://doi.org/10.1148/ryai.240225

McBain, R. K., Cantor, J. H., Zhang, L. A., Baker, O., & Zhang, F. (2025). *Competency of large
language models in evaluating appropriate responses to suicidal ideation: Comparative study*.
Journal of Medical Internet Research.

Moore, J., Grabb, D., Agnew, W., et al. (2025). *Expressing stigma and inappropriate responses
prevents LLMs from safely replacing mental health providers*. In Proceedings of the 2025 ACM
Conference on Fairness, Accountability, and Transparency.

Perez, A., Zhang, H., Ku, Y.-C., et al. (2025). *Privacy-preserving operating room workflow
analysis using digital twins*. In Medical Imaging with Deep Learning -- Short Papers 2025.

Sorin, V., Brin, D., Barash, Y., Konen, E., & Charney, A. (2024). *Large language models and
empathy: Systematic review*. Journal of Medical Internet Research.

Wong, D. (2026). *Deja vu in healthcare AI: Lessons from the world's pioneer AI clinical decision
support system*. BMJ Digital Health & AI.
