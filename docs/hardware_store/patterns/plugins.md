# Pattern family: Plugins and Adapters

*Eighth family doc for the Hardware Store's pattern shelf. Research basis: "Full-Stack Design Patterns
for CodeForge" (section 17, Plugin / Adapter Architecture), and the Software Parts directive's family
10 (Plugin and Adapter Parts).*

## Provenance

- **Origin:** `independently_implemented_pattern`. The plugin/registry pattern (extend an application
  by registered modules implementing a contract) is documented. **No code was copied**; the behavior
  was reimplemented from first principles.
- **Independently implemented:** the registry, the metadata/capability validation, the enable/disable
  model, the explicit trust boundary, and both adapters.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `plugin-registry`

`parts/shelf/plugin_registry.py` -- a generic `PluginRegistry[P]`. `register(info, plugin)` validates on the
way in (a duplicate name is refused; a plugin missing a capability the registry `requires` is
refused); `disable`/`enable` toggle a plugin; `get`/`active` return only enabled plugins. **The trust
boundary is explicit and safe by construction: it never imports or executes arbitrary code** -- the
caller passes an already-constructed object.

**Invariants (tested):** register-then-get round-trips; a duplicate name or a missing required
capability fails loud; a disabled plugin is never returned; mutating an unknown plugin is loud while
`get` is lenient (None). Per the directive: no arbitrary code loading; explicit registration,
capabilities, and documented boundaries only.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** pluggable in-world heralds (`parts/heralds.py`).
- **Core behavior:** register named extensions and dispatch to the enabled ones.
- **Game-specific presentation:** the `heralds` verb shows active proclamations.
- **Reusable domain logic:** the whole `PluginRegistry` (game-free).
- **Practical applications:** exporters, notification providers, storage backends, integrations.
- **Required abstraction:** a registry keyed by name with metadata; already in the core.
- **Adapters required:** a game verb; a practical provider hub.
- **Security implications:** admit extensions only by explicit registration + capability checks.
- **Testing implications:** duplicate/disabled/capability paths.
- **Hardware Store candidate:** YES (stocked as `plugin-registry`).

## Adapters (one core, two lives)

- **Game:** `parts/heralds.py` -- heralds are plugins that each proclaim a line; `heralds` shows the
  active ones, and one can be disabled without touching the others. Tick-reachable.
- **Practical:** `parts/exporters.py` -- an `ExporterHub` registers export providers (json, csv), each
  `serialize`-capable, and dispatches by format name. New formats are added by registration.

## Evidence

- Tests: `tests/test_plugin_registry.py` (unit), `tests/test_heralds.py` (game + tick),
  `tests/test_exporters.py` (practical + a one-core proof).
- Manifest: `docs/hardware/plugin-registry.yaml`. Trace it: `make loop PART=plugin-registry`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no entry-point
  discovery or sandboxing; by design, no dynamic loading at all yet).

## Deferred (needs Josh's approval)

Entry-point discovery and any form of loading untrusted code (which would need a sandbox and a
reviewed trust model) are deliberate later junctures, not part of this slice.
