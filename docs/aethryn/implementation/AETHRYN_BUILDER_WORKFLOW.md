# Aethryn Builder Workflow

All commands run offline from the CodeForge repository root.

## Inspect and validate

```bash
PYTHONPATH=. .venv/bin/python -m tools.world explain veridia_greenhold_living_slice
PYTHONPATH=. .venv/bin/python -m tools.world validate-packet \
  content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml
PYTHONPATH=. .venv/bin/python -m tools.world canon-check
PYTHONPATH=. .venv/bin/python -m tools.world map-concordance-check
PYTHONPATH=. .venv/bin/python -m tools.world economy-check
PYTHONPATH=. .venv/bin/python -m tools.world ecology-check
PYTHONPATH=. .venv/bin/python -m tools.world find-orphans
```

The existing survey commands remain available:

```bash
PYTHONPATH=. .venv/bin/python -m tools.world validate
PYTHONPATH=. .venv/bin/python -m tools.world find-unreachable
PYTHONPATH=. .venv/bin/python -m tools.world graph
```

## Compile to staging

```bash
PYTHONPATH=. .venv/bin/python -m tools.world compile-packet \
  content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml \
  --output /tmp/aethryn-veridia-package \
  --cache /tmp/aethryn-build-cache
```

Review `manifest.yaml`, `validation_report.yaml`, `records.yaml`, `world_ir.yaml`, and the room batch before
publication. The compiler refuses a packet with a validation error.

## Inspect provenance and compare artifacts

```bash
PYTHONPATH=. .venv/bin/python -m tools.world provenance living_sluice_wheel \
  --package /tmp/aethryn-veridia-package
PYTHONPATH=. .venv/bin/python -m tools.world diff \
  /tmp/aethryn-veridia-package \
  /path/to/previous/package
PYTHONPATH=. .venv/bin/python -m tools.world cache-inspect /tmp/aethryn-build-cache
```

## Publish directly after validation

```bash
PYTHONPATH=. .venv/bin/python -m tools.world materialize \
  content/seeds/aethryn/design/packets/veridia_greenhold_living_slice.yaml \
  --output /tmp/aethryn-veridia-package
```

`materialize` publishes by default after validation. Pass `--stage-only` when a packet needs a
separate staging review. Publication copies the batch into the active room-batch directory and
records a previous artifact under `.aethryn_rollbacks/` when one already exists.

To create a bounded hotfix after reviewing a candidate package:

```bash
PYTHONPATH=. .venv/bin/python -m tools.world hotfix \
  /path/to/base-package /path/to/candidate-package \
  --output /tmp/aethryn-hotfix
```

The hotfix directory contains `hotfix.yaml` and `changed_records.yaml`. It is a review artifact,
not an automatic publication command.

Room-batch records that describe an existing room are prose and metadata overlays. Their repeated
exit map is not applied to an assembled room unless `replace: true` is explicit. This keeps the
machine-readable topology and existing named connections authoritative, while still allowing a
packet to declare an intentional room replacement.

## Builder acceptance loop

1. Add or revise a design record and packet.
2. Run `validate-packet` and inspect every finding.
3. Compile to a clean staging directory.
4. Compare the output digest to the expected rebuild.
5. Run the focused tests and `world validate`.
6. Human reviews canon status, lore, topology, and publication scope when the packet is promoted.
7. Retain the rollback artifact after direct publication.

Never turn a generated packet into canon by changing its status as part of compilation.
