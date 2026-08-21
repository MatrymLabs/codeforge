# WO-COLD-1 Bench Report

## Pre-run reading, before execution

- First sentence I did not understand: the README says the Hardware Store is “patterns proven in
  play and translated into real software,” but does not explain the translation boundary.
- First claim I did not believe: “Every command here is real, tested, and reachable in the game.”
  It is a broad claim without a command-by-command proof in the README.
- Expected `make deploy-proof` behavior: run the deploy script, pour a standalone Aethryn cast,
  boot it in a fresh subprocess, exercise play commands against its own world, and print a verdict.

## Execution

The clone was made from the public URL into a disposable directory with no shared
repository tree:

```text
git clone https://github.com/MatrymLabs/codeforge "C:\Users\jevan\AppData\Local\Temp\cf-cold-probe-328d7fbc9a204ef6a5c8ce456da15caf\codeforge"
exit 0
wall-clock: 4.478s
```

The clone needed `git`, `make`, and `uv` on PATH. The instruction names only `git`
and `make`; `make env` supplied the Python environment through the already-present
`uv` executable. No installation was performed by this probe outside the clone's
environment setup.

Before running the proof, `make env` was run exactly as invited:

```text
make env
exit 0
wall-clock: 6.259s
output: uv found - fast env build; Creating virtual environment; venv ready
```

The target read before execution was:

```make
deploy-proof:
        @$(PY) scripts/deploy_aethryn_seed.py
```

That matched the expectation: it poured the cast, booted a fresh subprocess, ran
play commands, and printed a deployment verdict.

## Three proof runs

Each run was executed in the same clean clone after `make env`; each exited 0 and
produced a report with `boot verdict: BOOTED + SERVED`, `world at boot: 10681 rooms
(spawn: veridia)`, and `label: DEPLOYABLE`.

```text
run 1: make deploy-proof   exit 0   2.671s
run 2: make deploy-proof   exit 0   2.388s
run 3: make deploy-proof   exit 0   2.502s
```

The observed result matched the pre-run expectation. The only expectation boundary
is semantic: this is a local cast deployment proof, not evidence that a public
stranger will find the README credible.

## Falsification attempts

### Cast independence

The deployment script was also run with a persistent destination so the cast could
be tested after the source clone was renamed:

```text
.\.venv\Scripts\python.exe scripts/deploy_aethryn_seed.py 2026-08-21 C:\Users\jevan\AppData\Local\Temp\cf-cold-probe-328d7fbc9a204ef6a5c8ce456da15caf\persistent-cast
exit 0
wall-clock: 2.190s
```

The source clone was then renamed from `codeforge` to `codeforge-source-renamed`.
The original path no longer existed. Booting the persistent cast after that rename
returned:

```text
(True, 'OK: 4 commands ran clean')
exit 0
wall-clock: 1.004s
```

The cast therefore survived removal of its original source path and served its
commands independently. The cast manifest still records `detached: false` and
`isolation_proven: false`; those fields correctly limit this finding to the
observed boot-after-rename test, not a claim of a formally isolated production
artifact.

### What 10681 counts

The authored `content/blueprints/aethryn/rooms.yaml` contains 77 room entries.
The cast's runtime loader returned 77 entries from that file, but the final
`kernel.world.world.WORLD` dictionary contained:

```text
{"rooms": 10681, "start_room": "veridia"}
exit 0
wall-clock: 0.556s
```

The world module merges the authored rooms with generated road, wildlands, fields,
dungeons, settlements, inns, stores, authored towns, and workshop content. Thus
10,681 is an honest final runtime-world room count, not a raw YAML row count. The
word “rooms” is supported by the runtime dictionary size, with the important
qualification that most of the final world is procedurally/generated content.

## Verdict

Three cold-context runs reproduced the proof, the cast booted after the source
clone was renamed, and the 10,681 figure was traceable to the runtime world rather
than misreported source rows. This supports the operational claims, while not
proving that an unrelated human reader will find the prose credible.

VERDICT: CREDIBLE AS WRITTEN

status: COMPLETE
