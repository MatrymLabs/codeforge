# Seed Manifest → Job → Evidence Slice

This slice connects an engineering `SeedManifest` to the existing Creator Workshop job service and durable evidence store.

It deliberately reuses:

- `kernel.seedlab.workshop_services.CreatorWorkshopService` for the real bounded test job;
- `kernel.seedlab.jobs.FileJobStore` for restart-safe job records;
- `kernel.hardware_lifecycle.HardwareRegistry` for governed lifecycle state;
- `kernel.hardware_activation.activate_hardware_component` for explicit runtime activation;
- `kernel.seedlab.event_bridge` for typed Seed events and audit correlation.

The new adapter is `kernel.seedlab.manifest_evidence`.

## Contract

`SeedManifest` records the Seed, source, target profile, and required Hardware IDs. The adapter validates that every required component is already `active`; it never installs or activates a component implicitly.

After that gate succeeds:

1. Creator Workshop runs the existing named, bounded `TestJob`.
2. The job is persisted in the existing `FileJobStore`.
3. The job completion event is published through the existing Seed event bridge.
4. `ManifestRunEvidence` durably links the manifest digest, Seed, job, event, status, target profile, and required components.
5. A `manifest.test.completed` event exposes the linkage to future Master Client and Creator Console consumers.

The evidence store is append-safe: re-saving identical evidence is allowed, while conflicting content for the same evidence ID is rejected.

## Safety boundary

Discovery, installation, activation, execution, and evidence remain separate actions. A missing, installed-but-inactive, or unknown component blocks execution with an actionable error. This prevents a manifest from silently turning catalog presence into runtime authority.

## Validation

```text
tests/test_manifest_job_evidence_slice.py
```

The tests cover blocked execution before activation, durable restart recovery, event linkage, and reuse by Aethryn plus a second Seed.
