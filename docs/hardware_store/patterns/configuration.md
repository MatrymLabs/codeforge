# Pattern family: Configuration and Feature Control

*Sixth family doc for the Hardware Store's pattern shelf. Research basis: "Full-Stack Design Patterns
for CodeForge" (section 14, Feature Flags; section 18, Configuration Management). This doc covers the
feature-flag part; typed settings already ship as the separate `typed-settings` part.*

## Provenance

- **Origin:** `independently_implemented_pattern`. Feature flags (LaunchDarkly: "enable or disable a
  feature without modifying source code or redeploying") are a documented pattern. **No code was
  copied**; the behavior was reimplemented from the concept.
- **Independently implemented:** the registry, the override-beats-default precedence, retirement, the
  reproducible snapshot, and both adapters.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `feature-flags`

`parts/feature_flags.py` -- a `FlagRegistry` of named flags with defaults. `is_on` returns the
override if set, else the default; `enable`/`disable`/`reset` manage overrides; `retire` removes a
flag (flag retirement); `snapshot` gives the reproducible current state. An **unknown flag is an
error, never silently off**, and flags **default off** so beta content never ships on by accident.

**Invariants (tested, incl. property-based):** both on and off paths are reachable; an override
always wins and reset returns to the default; an unknown or duplicate flag fails loud; the snapshot
is reproducible. Flags **gate features; they are not authorization.**

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** an in-world feature panel (`parts/features.py`).
- **Core behavior:** register named flags and answer is-this-on at runtime.
- **Game-specific presentation:** a `features` panel of beta_quests / verbose_combat / debug_mode.
- **Reusable domain logic:** the whole `FlagRegistry` (game-free).
- **Practical applications:** canary releases, A/B tests, kill switches, operational toggles.
- **Required abstraction:** a flag registry + a precedence rule; already in the core.
- **Adapters required:** a game panel; a practical env-driven control.
- **Security implications:** an emergency kill switch; never confuse a flag with an access check.
- **Testing implications:** both flag paths exercised; precedence and retirement.
- **Hardware Store candidate:** YES (stocked as `feature-flags`).

## Adapters (one core, two lives)

- **Game:** `parts/features.py` -- the `features` verb shows the world's flags; `feature_on(name)`
  lets other game code gate behavior. Flags default off. Tick-reachable.
- **Practical:** `parts/feature_control.py` -- `FeatureControl` where an environment variable
  (`FEATURE_<NAME>`) overrides the default (the 12-factor precedence). A kill switch without a redeploy.

## Evidence

- Tests: `tests/test_feature_flags.py` (unit + property), `tests/test_features.py` (game + tick),
  `tests/test_feature_control.py` (practical + a one-core proof).
- Manifest: `docs/hardware/feature-flags.yaml`. Trace it: `make loop PART=feature-flags`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no percentage
  rollouts or targeting yet).

## Deferred (needs Josh's approval)

Percentage rollouts, targeting rules, and a hosted flag service are later slices.
