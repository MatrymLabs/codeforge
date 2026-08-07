# Aethryn Crafting and Professions

Rich recipes are projected into the existing `craft <recipe>` executor. Each has a stable id,
output, positive inputs, one profession, one station, time, output quantity, quality logic, and
provenance. Catalog professions are merged into the persisted practice-based profession registry;
they do not create a second skill system.

Veridia uses smithing, alchemy, woodcraft, woodcutting, and tailoring alongside existing authored
trades. Stations are placed selectively: smelter, anvil, repair bench, woodworking bench, and field
alchemical bench. Recipes are reachable from source materials and every station reference exists.

Quality is bounded by material/workshop/skill causes. Repair and salvage return to the same material
loop, with source-item restrictions and no unique-item salvage. Circular or source-free recipes are
reported as actionable validation findings.

Recipe knowledge is represented by the current recipe/profession data and persisted practice. The
material catalog does not answer unresolved canon through recipe discovery.
