# codeforge-edge (Go)

A transparent TCP **edge gateway** in front of the Python game gateway (`adapters/gateway.py`). It
accepts client connections and byte-proxies each straight through to the gateway -- one goroutine per
direction -- without ever inspecting the stream, so telnet/IAC negotiation stays end-to-end.

This is the **first service organ** (ADR-0011): an out-of-process polyglot component behind a
Python-first fallback. When this binary is not built, `parts.edge.EdgeProxy` (the identical proxy,
thread-per-connection) carries the game and `make check` is green. Nothing depends on Go being present.

## Why Go here

The Python gateway is thread-per-connection with a ceiling (`MAX_CONNECTIONS = 128`) because that
model does not scale to a large connection flood. Go's goroutines do: a few KB per goroutine versus
~8KB+ of stack per OS thread. The edge holds the connections; the game logic stays in Python.

## Build

```sh
go build -o codeforge-edge .     # from native/edge/
```

The binary is git-ignored; `go.mod` is committed. Standard library only, so there is no `go.sum`.

## Run

```sh
./codeforge-edge -listen 0.0.0.0:4001 -backend 127.0.0.1:4000
```

It prints `READY <bound-addr>` on stdout (machine-readable, resolves `:0` ephemeral ports) and a
friendly line on stderr. Or launch through Python, which picks this binary when built else the
reference: `python -m parts.edge --listen 0.0.0.0:4001 --backend 127.0.0.1:4000`.

## Test

```sh
go test ./...                    # round-trip, 200 concurrent conns, unreachable-backend
```

Parity against the Python reference and the connection-scaling benchmark live in the Python repo:
`tests/test_edge.py` and `benchmarks/bench_edge.py`.

## Evidence

Concurrent-connection flood, Go vs the Python reference (Pi, 2026-07-28): ~1.6x at 50 connections
rising to **~2.8x at 400**. A connection-boundary win, not a CPU-compute win -- labelled honestly.
