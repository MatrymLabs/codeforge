# ADR-0016: Live Hardware status and world-event observation

Status: Accepted

## Decision

The gateway exposes one read-only `Hardware.Status` GMCP projection to authenticated owner
clients. The projection is produced by the injected `HardwareRuntimeController`; the Master Client
does not infer activation from catalog metadata and cannot mutate lifecycle state through this
package.

The shared client `PanelHost` registers `hardware_runtime` against `Hardware.Status`. The TUI and
Qt shells therefore render the same text-first, accessibility-safe view. Until the package arrives,
the panel reports that status is unavailable rather than inventing an empty runtime.

World announcements remain authoritative in the existing world event bus. A gateway may bind the
active `event-ledger` runtime provider as an observation sink. The sink receives typed
`codeforge.seed-event` envelopes for room announcements, structured room frames, cohort messages,
and broadcasts. If no ledger is active, or if the observation sink fails, world delivery continues;
observation is not allowed to discard a player action.

## Boundaries

- Hardware installation and activation remain governed operations owned by the runtime controller.
- `Hardware.Status` is owner-facing because provider and consumer information is operational state.
- Event-ledger records are evidence and audit projections, not a second source of world authority.
- `Hardware.Status` and event envelopes are versioned protocol surfaces and must retain text
  fallbacks for clients that cannot render structured panels.
- Gateway shutdown removes its exact world-event binding so a stopped gateway cannot retain a global
  observer.

## Validation

- CodeForge event and runtime tests cover live envelope routing and sink-failure isolation.
- Gateway tests cover the read-only status projection with an injected runtime.
- Client tests cover malformed status handling, capability gating, and shared panel rendering.
- Full socket integration tests require local socket access in restricted environments.
