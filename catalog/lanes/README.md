# Ecosystem provisioning records

Machine-readable records live in `_schema.yaml` and the lane YAML files in this directory.

These records answer how an ecosystem can be provisioned reproducibly. Governance remains in the
Workshop's census-backed `hardware-store/LANGUAGE_LANES.yaml` register; `provisioning_status` is a
separate vocabulary and must not be renamed to `status`.

`verified_on` is evidence, not a promise. It is populated only when the commands in that record
were actually run on this Bench. Candidate and deferred ecosystems retain a null date. The
registry intentionally has records for the 13 current governance lanes plus candidate SQL Server
and MySQL engines; the contract is one-way from governed lanes to provisioning records.
