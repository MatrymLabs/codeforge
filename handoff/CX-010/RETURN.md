packet_id: CX-010
status: PARTIAL
tests_passing: no

## Verification

The amended journey assertions are now invariant-based. Targeted amended tests passed:

```text
export PATH="$PWD/.venv/bin:$PATH"
pytest -q tests/test_journey_aethryn.py tests/test_journey_spine.py tests/test_quest.py
.............................                                            [100%]
29 passed in 1.93s
```

The full required gate was run with refreshed Go tooling and writable caches:

```text
export PATH="$HOME/.local/go/bin:$HOME/go/bin:$PWD/.venv/bin:$PATH"
export GOCACHE=/tmp/codeforge-gocache
export GOLANGCI_LINT_CACHE=/tmp/codeforge-lintcache
timeout 900s make check
```

The gate reached the complete 5264-test parallel suite but did not produce a completed verdict in
this session. The captured run remained at 76% after earlier known failures, so this is UNVERIFIED,
not a green claim. The command to resolve it is the exact gate above on a host where the full suite
can complete.

`git rev-list --count HEAD..origin/main` was 0 before implementation. The founder's banking
question is noted, not implemented: the clamp discards remainder XP by current design.

Both reuse tiers were searched for clamp, cap, rate limit, and progression; no applicable Part was
found or consumed.

`git diff --stat` is limited to the amended allowlist: quest implementation, quest tests, both
journey tests, and this RETURN. No map or quest generator was touched.

Pattern screen: lane echo (persistence, commands, events, transactions, world graph, integration):
quest progression integration observed. Catalogue match: none. Recurrence check: none. Verdict
note: domain-specific reward clamp, no extraction candidate.

Extraction block: none observed. Unverified: full `make check` completion and CI verification.
