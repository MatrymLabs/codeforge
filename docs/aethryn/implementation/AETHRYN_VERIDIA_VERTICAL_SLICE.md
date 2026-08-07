# Veridia Vertical Slice

Packet: `veridia_greenhold_living_slice`

The first compiler slice is deliberately small and local. It extends existing authored Greenhold
content with a civic edge, a farm edge, a road threshold, a wilderness loop, and a shallow hazardous
service hollow. It does not alter the fourteen-region graph or create a new regional route.

## Living mechanism

```text
Greenhold water and waste edge
        -> road and drainage
        -> barley and meadowfoil work
        -> trader and miller dependency
        -> boar and vermin pressure
        -> shallow old service hollow
        -> reversible cistern status
```

The packet contains 9 rooms. The anchor preserves existing Greenhold named exits and adds a south
connection. New rooms have reciprocal links and form a local return loop. The room batch is ordinary
CodeForge seed data, so text clients can traverse it through the existing room and command path.

The sidecar defines 3 NPC roles and schedules, 2 creature ecology records, 2 notable objects, 2
resource nodes, 3 economy flows, 2 ecology flows, 3 quest pressures, 1 dungeon record, and 1
reversible state record. Quest causes are pressures, not a large prewritten quest list.

## Canon posture

The slice uses current Greenhold authored material and leaves global questions unresolved. The pale
sluice wheel is described by material, geometry, behavior, input, output, failure mode, local
interpretation, and understanding level. It is not explained as generic magic. No record promotes
itself into canon.

## What is demonstrated now

- complete design hierarchy and room navigation;
- reciprocal local exits and a threshold into a connected wilderness loop;
- settlement water, waste, food, fuel, labor, services, and trade dependencies as validated records;
- NPC roles and schedules as provenance-bearing records;
- creature habitat, recurrence, pressure, and civilization relation;
- economy and ecology flows;
- pressure-driven quest causes;
- CodeForge-compatible room-batch output;
- deterministic rebuild and package digest;
- reversible cistern state persisted through a restart-safe state seam and projected into text;
- authored valve-key retrieval followed by packet-declared `maintain cistern` repair;
- resolved water-shortage pressure removed from the live projection after repair;
- direct publication with rollback, plus an explicit stage-only path.
- read-only runtime projection of compiled routines, flows, ecology, and local pressures.

## Deliberate limitations

The current runtime loader projects batch occupants and objects but does not simulate movement,
production quantities, inventory depletion, or ecology population changes. Those records remain
validated compiler output, while `aethryn_runtime.py` projects their routines, flows, ecology
pressure, and quest pressure as read-only room signals. `WorldStateStore` proves persistence and
text projection for the cistern seam in the live room renderer.
