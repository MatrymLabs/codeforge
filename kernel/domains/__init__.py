"""Domain modules: the optional, per-Seed units that carry domain-specific capability.

A domain module satisfies the neutral `kernel.seedlab.domain.DomainModule` contract and registers
itself into a `DomainModuleRegistry` at composition time. The domain-neutral platform
(kernel/seedlab) NEVER imports this package -- an import-linter contract enforces it -- so a Seed
that selects no domain module (or a different one) never loads code it did not ask for. A module
MAY depend on its own domain (a future game module on kernel/world); the education module is
stdlib-only.
"""
