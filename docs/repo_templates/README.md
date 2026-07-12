# Repository template library

Reference layouts for project types CodeForge **does not need yet**. These are documentation,
not live directories: per the architecture doctrine, we do not create empty folders to look
mature. When CodeForge (or a sibling on the ship) actually grows one of these shapes, the
template here is the starting point, and ADR-0007 gets a status update.

Each template answers the same question for a different archetype: *where does each kind of file
belong?* They are distilled from "Repository & File Structure Best Practices: Python and
Multilanguage Stacks" and cross-checked against the authoritative sources it cites (PyPA, Maven,
Go, Rust, GitHub/GitLab CI docs).

## What CodeForge uses today

CodeForge itself is the **single-package Python flagship** archetype: a flat importable `parts/`
package plus a root `forge.py` tick, self-installed, monorepo-style, framework-earns-its-place.
That live structure is recorded in [ADR-0007](../adr/0007-repository-layout.md), not duplicated
here. These templates cover the shapes it might grow *into* or spawn *beside*.

## Templates

| Template | Use when | Status for CodeForge |
|----------|----------|----------------------|
| [full_stack.md](full_stack.md) | a Python backend gains a JS/TS front end | **planned, not present** (no front end yet) |
| [infrastructure.md](infrastructure.md) | deployment moves beyond the Render demo (Terraform/k8s) | **deferred by design** (see DEVELOPMENT_PLAN) |
| [library_package.md](library_package.md) | a `parts/` subsystem is extracted to publish on PyPI | **not yet** (no part is externally reused) |
| [data_science.md](data_science.md) | a research/analysis repo with notebooks + datasets | reference only |

## Rule of use

A template is a starting point, never a mandate. Adopting one is a repo-architecture decision
(a critical juncture): it gets its own ADR or an ADR-0007 status update, a migration plan with
rollback, and Josh's go/no-go. Copying folders from a template into the live tree "to look
ready" is exactly the empty-folder anti-pattern this library exists to prevent.
