# DISPATCH CX-023

```yaml
packet_id:            CX-023
title:                Group the dependency ecosystem that produces four PRs a week
stream:               fleet-ops
owner:                Codex
reviewer:             Claude Code, who re-runs every command independently
merges:               founder
size:                 small
taint_class:          SAFE. No studied external material. This repository's own Dependabot config.

goal: >
    Group codeforge's Python dependency updates so a week's bumps arrive as ONE pull request instead
    of four, and merging the first does not force a branch update and a full re-run on the other
    three.

    THE INVARIANT, in prose and separate from the commands that test it: a week of routine
    dependency updates costs one review and one CI cycle, not one per package. The rule already
    exists in this file for one action; it was never generalised to the ecosystem that actually
    produces the volume.

why_now: >
    Measured 2026-08-13. Six Dependabot PRs are open on this repository, all CLEAN, none merged:

      #937 pyproject.toml, uv.lock      #940 pyproject.toml, uv.lock
      #938 pyproject.toml               #941 .github/workflows/publish-image.yml
      #939 pyproject.toml, uv.lock      #942 .github/workflows/consume-first.yml

    FOUR touch pyproject.toml and THREE touch uv.lock. They serialise: merge one and the other three
    go BEHIND, and `required_status_checks.strict` is on, so each then needs a branch update and a
    full seventeen-check re-run. Merging by hand is six sequential CI cycles and the same pile
    arrives next week.

    This repository already learned the rule and applied it to exactly one action. `dependabot.yml`
    carries the reasoning in its own comment:

      "codeql-action's init, analyze and upload-sarif are ONE action published from one repo, and
       they refuse to run at different versions... Ungrouped, Dependabot opened a PR per sub-action
       (#879, #880, #881); each was red on its own and merging any one of them turned main red once
       already (#857)."

    That is the gate standard's rule 4, "one dependency gets one PR", learned the expensive way. It
    was never extended to the `uv` ecosystem, which is where the four-a-week volume comes from.

the_design: >
    Settled so implementation does not decide it.

    1. The `uv` ecosystem gains a group. Minor and patch updates travel TOGETHER in one PR.

    2. MAJOR updates stay UNGROUPED, one PR each. A major is a version event that deserves its own
       review and its own rollback; folding majors into a batch is how a breaking change rides in
       behind four safe ones. Dependabot expresses this with `update-types` on the group.

    3. `codeql-action`'s existing group is UNTOUCHED, and its comment stays. It solves a different
       problem, sub-actions that must move in lockstep, and the reasoning in that comment is the
       evidence for this order.

    4. The github-actions ecosystem is NOT grouped by this order. Two of the six open PRs are
       actions (#941, #942) and they touch different workflow files, so they do not serialise.
       Grouping them is a defensible later call and is out of scope here.

out_of_scope: >
    MERGING THE SIX OPEN PRs. Do not merge them. Once the group lands, Dependabot recombines the
    Python ones on its next run, and the recombined PR is what gets reviewed. Merging first and
    grouping after pays the six-cycle cost this order exists to avoid.

    THE OTHER TWELVE REPOSITORIES. Measured: eight of them carry `codeql-action` as their only group,
    so the gap is Workshop-wide, but only codeforge has an open pile. One packet, one repository.
    Note the pattern in the RETURN as a signal; do not fix it here.

    Any change to what CI runs, to `required_status_checks`, or to the update interval.

preconditions: >
    CHECK: file .github/dependabot.yml contains codeql-action
    CHECK: file .github/dependabot.yml contains package-ecosystem
    CHECK: file .github/dependabot.yml lacks update-types

contract_tests: >
    No new test code; a Dependabot config has no unit under test and the real proof is a future PR.
    What the RETURN must carry instead:

      the config parses as valid YAML, shown with a command
      `gh api repos/MatrymLabs/codeforge/dependabot/alerts` or the Dependabot config view showing
      GitHub accepted the file rather than silently ignoring it
      the group's `patterns` and `update-types` quoted in the RETURN, so a reviewer sees what was
      grouped and what deliberately was not

    A malformed dependabot.yml is accepted into the repository and silently disables updates. That
    failure is invisible until the bumps simply stop arriving, so the acceptance check is the point.

verification_command: |
    cd codeforge
    python3 -c "import yaml,sys; yaml.safe_load(open('.github/dependabot.yml')); print('dependabot.yml parses')"
    make check

definition_of_done: >
    The `uv` ecosystem carries a group covering minor and patch; majors remain ungrouped; the
    codeql-action group and its comment are unchanged; the config parses and GitHub reports it valid;
    `make check` green; the six open PRs left alone and named in the RETURN as awaiting recombination.

calibration_required: >
    This order cannot be calibrated by sabotage the way a gate can: the instrument is GitHub's
    scheduler, not a command here. Say so plainly in the RETURN rather than inventing a red-green
    transition that proves nothing.

    What CAN be shown, and must be: a deliberately malformed group (a bad key) is REJECTED by the
    YAML parse, and the valid one is accepted. That proves the verification command can fail, which
    is the honest half of the claim.

rollback: >
    Revert the commit. Dependabot reads the file on its next run; reverting restores per-package PRs
    with no state to unwind.

approval_gates: >
    None beyond the founder's merge. No dependency is added, removed or bumped by this order. It
    changes how updates are BATCHED, never which updates arrive.

store_search_result: >
    Both tiers searched 2026-08-13; one tier logged is an incomplete search.
    Certified Tier (hardware-store/catalog/, 20 cards: 3 CERTIFIED, 4 CANDIDATE, 13 STUDIED): nothing
    addresses dependency update policy. `source-monitor` classifies what changed at a watched source
    and is the nearest by shape, but it monitors a source and does not batch updates from one.
    Working Shelf (codeforge/catalog/parts.yaml, 104 entries): `workflow-linter` statically lints a
    parsed GitHub Actions workflow for over-broad permissions and unpinned actions. It reads CI YAML,
    which is adjacent, and it does not read dependabot.yml or express batching policy.

    Verdict: NO PART EXISTS and none is warranted. A Dependabot group is configuration, not a
    mechanism. First occurrence, logged only.

parts_to_consume: >
    None. See store_search_result.

watch_for: >
    A MALFORMED dependabot.yml IS ACCEPTED SILENTLY. GitHub does not reject the push; updates simply
    stop arriving, and nobody notices until a CVE lands in a dependency nobody bumped. That is why
    the RETURN must show GitHub accepting the config, not merely that the file parses locally.

    Second: grouping ALL updates including majors would be the wrong fix and the tempting one. A
    single breaking major inside a batch of four safe patches turns a routine merge into an
    investigation, and the batch cannot be partially merged.

blast_radius: >
    Run before this allowlist was fixed.

      grep -rn 'dependabot' .github/workflows/ Makefile
      -> no workflow and no make target reads dependabot.yml. Nothing in CI depends on its contents.

      for each of 13 repos: count package-ecosystem and groups in .github/dependabot.yml
      -> 13 repos carry a dependabot.yml. Eight have exactly ONE group and it is `codeql-action` in
         every one; four have none. The Python ecosystem is ungrouped Workshop-wide.

      gh pr list --author app/dependabot, all 13 repos
      -> codeforge 6 open. Every other repository: 0.

    What that surfaced: the file has no readers inside CI, so the change cannot break a gate; the gap
    is Workshop-wide but the PILE is codeforge-only, which is why out_of_scope forbids fixing the
    other twelve here; and the six open PRs are the population this order deliberately does not
    touch.

file_allowlist:
  - .github/dependabot.yml                     # the uv group; codeql-action untouched
  - handoff/CX-023/RETURN.md                   # NEW, explicitly authorised
```
