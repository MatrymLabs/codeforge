# CodeForge integration repairs

The current platform keeps one source of truth per boundary:

- SeedLab persists engineering Seed identity in its `SeedStore`.
- `kernel.seedlab.runtime_bridge.bind_runtime_seed()` verifies that identity against the
  canonical `content/seeds/<id>/world.yaml` package before runtime use. It checks the stable id,
  but never imports or executes package code.
- Creator Workshop drafts remain per-session memory. An explicit `publish` writes an atomic,
  validated JSON overlay selected by `CODEFORGE_WORKSHOP_STATE` (or the operator's CodeForge
  configuration directory). `kernel.world.world` replays the overlay after the base Seed and before
  link validation. Shipped Seed files are never rewritten.
- `kernel.hardware_activation.activate_hardware_component()` is the explicit bridge from an
  installed Hardware Store record to the existing `PluginRegistry`. Trusted platform code supplies
  the already-constructed plugin object; the bridge never dynamically imports a Hardware Card's
  source path. Disablement removes it from the runtime registry and records the governed state.

Activation is intentionally not automatic. Discovery, approval, installation, registration, and
runtime activation remain separate auditable actions.

## Test environment note

The managed Python image cannot complete AnyIO's cross-thread worker/portal wake-up. CodeForge's
API routes and observability middleware therefore use async/pure-ASGI boundaries, and API tests use
`tests/sync_test_client.py`, an in-thread `httpx2` ASGI adapter. This keeps route behavior real and
avoids a second server or a mocked response layer. Socket integration tests still require the
environment's network capability.
