# Hardware Store lifecycle

The Hardware Store has two related but distinct records:

- `catalog/parts.yaml` is the curated inventory of reusable capabilities.
- `docs/hardware/<id>.yaml` is the Hardware Card and machine-readable contract.
- `CODEFORGE_HARDWARE_REGISTRY` records explicit installation state.

The registry never imports or executes component source. A component must be present in the
catalog, have a Hardware Card, point to a real source file, and retain license/provenance metadata
before it can enter the lifecycle.

```text
discover -> validate -> approve -> install -> activate
                                      |          |
                                      v          v
                                  disabled <- active -> deprecated
                                      |
                                   rollback
```

Use the CLI for explicit operator actions:

```bash
codeforge hardware discover validator
codeforge hardware validate validator
codeforge hardware approve validator
codeforge hardware install validator
codeforge hardware activate validator
codeforge hardware list
```

Activation is never implied by discovery, approval, or installation. R&D experiments and
unregistered source cannot enter this registry automatically. Rollback preserves the lifecycle
history and returns the component to its previous state where the transition is safe.

The current registry is file-backed for local development and controlled deployments. Set
`CODEFORGE_HARDWARE_REGISTRY` to place it in the deployment data directory. A future database
adapter must preserve the same transition and audit contract.
