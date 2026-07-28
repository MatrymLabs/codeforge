# codeforge_nav — native world-navigation kernel (Rust / PyO3)

The first native organ of CodeForge's polyglot build. Rust used exactly where memory-safe systems
speed helps — bulk graph traversal at world scale — behind a narrow FFI, with a **pure-Python
fallback** (`parts/world/navigation.py`) kept in lockstep by a parity test.

CodeForge's world is a directed graph: rooms are nodes, exits are edges. This crate answers the
spatial questions fast:

- `NavGraph(edges)` — build a directed room-graph once from `(from_label, to_label)` exit edges.
- `.path(src, dst)` — shortest route (fewest exits) as room labels, or `None`.
- `.distance(src, dst)` — hop count, or `None`.
- `.reachable_count(src)` — how many rooms are reachable (compare to `.node_count()` for a
  connectivity audit of a million-room world).

## Build

```sh
# from this directory, with the codeforge venv active
maturin develop --release      # builds + installs the `codeforge_nav` module into the venv
```

CodeForge imports it opportunistically; when the compiled module is absent, the game falls back to
the pure-Python `NavGraph` with an identical interface, so nothing hard-depends on the native build.
The Python parity test (`tests/test_navigation.py`) pins the two implementations to identical
behaviour whenever the Rust module is present.
