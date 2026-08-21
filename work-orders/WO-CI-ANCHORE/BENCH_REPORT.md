# WO-CI-ANCHORE Bench Report

## Measure first

The workflow currently uses SHA-pinned Anchore actions:

```text
anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610
anchore/scan-action@e1165082ffb1fe366ebaf02d8526e7c4989ea9d2
```

The action metadata was inspected before editing. The available controls are:

```text
sbom-action: syft-version      available
scan-action: grype-version     available
scan-action: cache-db          available (Grype database cache, not binary cache)
binary caching:                no Anchore action input available
continue-on-error:             GitHub workflow step control, available
```

The actions do not expose a cache for the downloaded Syft or Grype binaries.
`cache-db` only caches the Grype vulnerability database. The workflow therefore
pins the tool versions and uses the observe-only failure policy for the Grype
step.

## Change

- Pin Syft to `v1.42.3`.
- Pin Grype to `v0.114.0`, the version currently pinned by the action source.
- Enable the available Grype database cache.
- Set `continue-on-error: true` only on the observe scan step.
- Upload SARIF only when the scan completed successfully.
- Always print either `MEASURED` or `UNMEASURABLE`; a download/scan failure is
  never rendered as a clean scan.

The job can therefore remain non-blocking for an Anchore download outage while
still stating that no vulnerability measurement occurred. A successful scan's
findings remain observable through the SARIF upload and action output.

## Verification

The verification command is the pull-request workflow run. This local bench has
no GitHub Actions runner, so no workflow result is claimed here.

status: READY_FOR_CI
