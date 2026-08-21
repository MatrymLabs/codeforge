# Ecosystem provisioning records

Machine-readable records live in `_schema.yaml` and the lane YAML files in this directory.

These records answer how an ecosystem can be provisioned reproducibly. Governance remains in the
Workshop's census-backed `hardware-store/LANGUAGE_LANES.yaml` register; `provisioning_status` is a
separate vocabulary and must not be renamed to `status`.

`verified_on` is evidence, not a promise. It is populated only when the commands in that record
were actually run on this Bench. Documented and candidate ecosystems retain a null date. The
registry carries the required records for the 13 governance lanes, candidate SQL Server and MySQL
engines, and the 16 ecosystems reserved for future Blueprint lookups; the contract is one-way
from governed lanes to provisioning records.
