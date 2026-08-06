# ADR-0015: Governed external script platform

Status: Accepted (2026-08-05)

## Context

The owner-only Lua console in ADR-0014 is a useful compatibility prototype, but an in-process
interpreter is not a multi-tenant security boundary. Creator scripts need durable contracts for
review, authorization, state, observability, and rollback, and the authoritative Seed must not
import creator source or expose host objects.

## Decision

Add `kernel.script_platform` as the platform boundary for future Creator Workshop and Hardware
Store runners:

- `ScriptManifest` and `ResourcePolicy` describe one immutable source revision, its scope,
  capabilities, provenance, state schema, and budgets.
- `ManifestValidator` rejects incomplete provenance and direct shell, process, filesystem, network,
  native, FFI, and import capabilities before a runner is selected.
- `CapabilityBroker` is deny-by-default, Seed-scoped, host-call bounded, and dispatches only to
  explicitly registered operations. It passes requests and typed data, never ORM or Seed objects.
- `InMemoryStateStore` and `FileStateStore` persist bounded, versioned JSON values with
  compare-and-set writes. Interpreter heaps and runtime bytecode are not authoritative state.
- `AuditLedger` stores bounded structured JSONL records with correlation IDs, resource data, and
  redacted output summaries.
- `ScriptRunnerSupervisor` launches a configured worker with `shell=False`, a minimal environment,
  a temporary working directory, bounded JSON output, and kill-on-timeout process-group cleanup.

The supervisor is intentionally honest about its boundary. Deployment must additionally provide a
separate UID or container, cgroups, filesystem isolation, network denial, seccomp, and an LSM
profile. Lua, Wasm, Python, or QuickJS runners are worker implementations, not permissions to
evaluate source in the Seed process. The ADR-0014 console remains owner-only until it is migrated
to a worker-backed runner.

Lifecycle is draft → validation → test → independent review → staging → activation, with
quarantine, disable, and rollback paths. This package supplies the contracts and enforcement seams;
it does not yet ship a Lua or Wasm worker image.

## Consequences

Positive: the same capability and state contracts can serve Aethryn and another Seed; worker
implementations can be replaced without changing Seed behavior; hostile requests are testable and
auditable; deployment security controls are explicit rather than implied by language restriction.

Cost: a production deployment still needs maintained worker images and OS policy, and the lifecycle
needs a durable registry/approval service before creator-facing activation is enabled.

