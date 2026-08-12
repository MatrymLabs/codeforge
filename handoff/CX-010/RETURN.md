packet_id: CX-010
status: BLOCKED
tests_passing: no

## Implementation

The single quest award site now clamps the reward to the current character's next-level threshold.
The map and all quest generators remain untouched. Added contract coverage proves a large reward
cannot advance more than one level and a modest reward is paid in full.

Targeted test evidence:

```text
export PATH="$PWD/.venv/bin:$PATH"
pytest -q tests/test_quest.py
.........................                                                [100%]
25 passed in 1.58s
```

Both reuse tiers were searched: `hardware-store/catalog/` for clamp, cap, rate limit, progression;
`codeforge/catalog/parts.yaml` for the same terms. No applicable Part was found or consumed.

## Required gate

The whole gate was run with Go and Go cache paths exposed and a 900 second cap:

```text
export PATH="$HOME/.local/go/bin:$HOME/go/bin:$PWD/.venv/bin:$PATH"
export GOCACHE=/tmp/codeforge-gocache
export GOLANGCI_LINT_CACHE=/tmp/codeforge-lintcache
timeout 900s make check
```

The run reached the full parallel pytest suite but had not completed by handoff. Earlier gate
output on this tree recorded six failures and multiple errors in the suite before the timeout;
the command was not converted into a passing claim. Therefore this order remains BLOCKED pending a
completed green gate and the live #910 reproduction transcript.

`git rev-list --count HEAD..origin/main` was 0 before implementation. Changed paths are limited
to the allowlist plus this RETURN; `.venv/` is pre-existing untracked environment state.

Pattern screen: lane echo (persistence, commands, events, transactions, world graph, integration):
quest progression integration observed; no unrelated recurrence. Catalogue match: none. Recurrence
check: no reusable pattern. Verdict note: domain-specific reward clamp, not an extraction candidate.

Extraction block: none observed. Unverified: full `make check` completion and the live #910 `north`
reproduction; rerun the exact command above after the current pytest run completes.
