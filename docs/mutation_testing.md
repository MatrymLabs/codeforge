# Mutation testing (the "Mutate" rung)

Coverage says a line *ran*; mutation testing asks whether a test would *notice if that line
were wrong*. A tool rewrites the code one small change at a time (a "mutant") and reruns the
tests: a mutant the tests catch is **killed**, one they miss **survives**. Survivors are the
honest signal - a place the suite is thinner than its coverage number implies.

## Run it

```
make mutation        # on-demand; scoped by cosmic-ray.toml (hashchain by default)
```

It prints the **surviving-mutant rate** (lower is better). A survivor is either a real test gap
(add a case that kills it) or an equivalent mutant (a change that cannot alter behavior - confirm
and move on). To mutate a different module, edit `module-path` and `test-command` in
`cosmic-ray.toml`.

## Why on-demand, never a CI gate

Mutation testing runs the test twin **once per mutant** (hashchain alone is 179 mutants), so it is
minutes, not seconds. That is fine for a deliberate deep-check but wrong for the PR path, which
must stay fast. So `make mutation` is a standalone rung: it is **not** part of `make check` and
**not** in CI. This matches the testing-forge scheduling insight - mutation/fuzz/chaos never
dominate the PR lane (see `docs/repository_maturity_scorecard.md`).

## Tool choice (honest)

`cosmic-ray` is the mutation tool because it is the one that **works on this Python 3.13 host**.
Both mutmut versions are broken here: 3.6 fails at import (its config loader raises before argument
parsing), and 2.5's pony-ORM backend is py3.13-incompatible (`cr-rate`-style reporting throws), and
a run left the source mutated in place. cosmic-ray installs and runs cleanly and reverts the source
after each mutant.

cosmic-ray is **not** in the default dev dependencies. Its transitive tree (aiohttp, gitpython)
would be installed by every `pip install -e ".[dev]"` - including CI, which never runs mutation.
So `make mutation` installs it just-in-time (`pip install cosmic-ray`) and hints if it is missing.
Tools are integrations, not identity: this one is pulled only when a human chooses to run it.

## Baseline (evidence)

First run, 2026-07-16, `parts/hashchain.py` (the published tamper-evident ledger, 14 hostile-case
tests):

- **179 mutants**, **~32% survived / ~68% killed**.

The survivors are the next real work: each is a mutation of the ledger that its current tests do
not catch. Some will be equivalent (e.g. a changed constant with no behavioural effect); the rest
name concrete cases to add. Killing them - and extending the config to more modules - is the
follow-on the tool now makes visible. The value is not the number; it is the *named* gaps.
