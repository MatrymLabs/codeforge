"""World Package (Layer 2): the game itself -- the transitive import closure of the seeded MUD.

These modules are the SEED's world: rooms, NPCs, items, combat, jobs, accounts, persistence,
the tick's session and derived math. They may import each other (`parts.world.*`) and the
Hardware Store (`parts.shelf.*`), but NEVER the platform/dev-tooling in `parts/*`. The one-way
dependency arrow (platform -> world -> shelf) is enforced by `parts/world_boundary.py`, wired
into the integrity ritual.
"""
