# Workspace Engineering Evidence

The versioned Seed workspace contract exposes an optional `Engineering.Evidence` package to the
CodeForge Master Client. It is a read-only projection of existing durable records:

- `manifest_runs` joins a validated Seed manifest to its real Workshop job and completion event.
- `hardware` reports the configured Hardware lifecycle records, including state and consumers.

The HTTP workspace endpoint reads these records from the existing evidence store and Hardware
registry. The endpoint does not create evidence, install components, activate plugins, rerun jobs,
or infer success from catalog presence. Activation remains an explicit governed operation, and a
manifest test remains blocked until every required component is already active.

The primary `bootstrap_platform()` path now registers the bundled Aethryn Seed idempotently in the
SeedLab registry, verifies it against `content/seeds/aethryn/world.yaml`, and validates that the
versioned workspace contract can be built. This closes the clean-checkout gap where the bundled
runtime existed but the ignored local SeedLab registry did not yet contain its record.

The client validates the package defensively and renders it through the text-first
`engineering_evidence` panel. The same package can arrive through the existing workspace/GMCP
transport; no second registry or runtime authority is introduced.

An absent package means the corresponding durable store is not configured or has no projection
source yet. An empty package is honest evidence that the configured source currently contains no
manifest runs or Hardware records.
