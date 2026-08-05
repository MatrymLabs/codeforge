# Bounded CodeForge validation

The normal `make test` and `make coverage` targets remain the CI-parity gates. When a local
environment leaves a gateway, worker, or API client alive, use the bounded diagnostics instead:

```text
make test-bounded
make api-bounded
```

`test-bounded` gives the ordinary non-property/non-fuzz suite 420 seconds. `api-bounded` gives the
API and gateway surfaces 180 seconds. A timeout returns exit status 124 and leaves the last pytest
output visible, so a caller can distinguish a hang from an assertion failure. These are diagnostic
deadlines, not permission to call a timed-out run passing; the timeout and remaining process/thread
leak must be recorded as an environment limitation until the offending test is isolated.

The targets use the existing pytest configuration and do not create a second test framework or
alter application timeouts.
