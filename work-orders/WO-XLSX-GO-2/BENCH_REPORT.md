# Bench Report: WO-XLSX-GO-2

## Break test

The staged proof passed without sabotage:

```text
synthesize: PASS
load: PASS
parse: PASS
SHEET Data
A1 | hello
B1 | shared
A2 | 42
B2 | TRUE
render: PASS
integrity: PASS
VERDICT: PASS
EXIT=0
```

Every stage failed under its sabotage flag:

```text
synthesize -> 1
load -> 1
parse -> 1
render -> 1
integrity -> 1
```

`integrity` re-hashes the source workbook and compares it with the synthesis digest before reporting
success. The proof is independently implemented in Go; it does not import or port the Python RF-001
proof.

## Pattern screen and reusable Part signals

- **lane echo:** synthesize/load/parse/render/integrity and per-stage sabotage match the evidence
  shape already required by the Workshop proof discipline.
- **catalogue match:** none observed in either Hardware Store tier.
- **recurrence:** two independent implementations of one staged proof shape (Python and Go) are a
  Fitting/Part candidate signal. This is intentionally not a shared abstraction or self-certified
  Part.
- **reimplemented:** the staged proof shape is independently reimplemented in Go.
- **recurrence:** every stage has a deliberate refusal path, including integrity.
- **generalizable:** deterministic text rendering plus source digest verification is reusable for
  converter products.
- **friction:** the requested root `go run ./native/sheets/proof` command has the same nested-module
  boundary as the root test command; the module-local `go run ./proof` is the verified equivalent.

## Awaiting Principal Engineer

The proof is ready for review. The Go standard-library vulnerability and nested-module command
boundary are the open decisions recorded by WO-XLSX-GO-1.
