# RetroForge Design

**Status:** RF-001A scaffold, 2026-08-13. Active Build, parallel lane, canon section 6a.

RetroForge is a CodeForge capability for retro ROM inspection, graphics decoding, and Seed-ready
asset extraction. The Rider plugin is its first projection. **The Rider plugin is not the product.**

## Why this exists, and why it is not a new direction

The Hardware Store already holds **thirteen STUDIED cards** filed from *INTAKE RUN 01 BODY 3, the
ROM Hacking Research Lane Charter*, every one clean-room and `taint_class = SAFE`:

```text
bank-and-memory-map (PRT-0017)   palette-discipline (PRT-0013)
tilemap-bit-packing (PRT-0009)   offset-per-tile (PRT-0019)
metatile-hierarchy               compression-as-data-design
dictionary-text-encoding         constrained-map-streaming
layer-composition                sprite-budget
frame-time-budget                voluntary-budget
checksummed-save-slot
```

`STUDIED` means pattern with no code. The Store's own gate prints twenty-six
`pattern has no code` warnings, and thirteen of them are these. **RetroForge is the first code
consumer of research this Workshop already chartered and then left on the shelf.** That is the
case for the lane: not a new direction, a maturation path.

## Layering, and the one rule that holds it

```text
kernel/retroforge/            core: artifact truth. Python. UI-independent.
  binary.py                   read-only bounds-checked byte window
  artifact.py                 RomArtifact: immutable bytes + checksum
  codec.py                    TileCodec, PaletteCodec, AddressMapper, RomPlatformModule
  manifest.py                 ExtractionManifest: what came from where
  platforms/                  one module per console. NES first.

native/rider-retroforge/      projection: Kotlin + Gradle. Draws what the core decoded.
```

**Decoding logic does not live in UI classes.** The Rider plugin calls the core and owns no format
knowledge. Every other rule here follows from that one.

## Design decisions worth defending

**A decoded tile is indices, never colours.** Indexing is the retro graphics model: the tile says
"colour 3" and the palette decides what colour 3 is. Collapsing them would make every palette swap
a re-decode.

**`detect()` returns confidence, not a boolean.** The charter names auto-detection that overpromises
as a risk. A headerless `.bin` is a plausible Genesis ROM and a plausible several other things;
`0.4` says that honestly and `True` does not.

**`AddressMapper` may return `None`.** `bank-and-memory-map` names the failure mode directly: a
pointer crossing a bank boundary without a switch. Returning `None` beats inventing an offset.

**The read-only promise is a property of the type.** `ByteSource` exposes no mutation, so "no ROM
bytes were modified" is enforced by the type the decoders are handed rather than by everyone
remembering. An out-of-range read raises `OutOfRange`; it never truncates, because a short read
decodes garbage into a tile that looks like real data.

**Every asset carries the source checksum, duplicated deliberately.** Assets get split out of
manifests and pasted elsewhere. One that travels without provenance is what the manifest exists to
prevent.

## Safety model, RF-001

Read-only except generated output. **No ROM bytes are modified, ever, in this Work Order.**

Principal Engineer ruling D-9, 2026-08-13: **analysis is unbounded, the repository stays clean.**
Decode, map and inspect whatever the published formats allow. No ROM bytes enter git and no preview
derived from a commercial ROM is committed, because `codeforge` is the public flagship. **Test
fixtures are synthetic bytes**, and every test RF-001 needs can be built from them: the NES 2bpp
rule is checkable with sixteen hand-written bytes.

Editing is a later Work Order and does not start until undo, dirty state, safe-write and explicit
save are specified.

## Toolchain

No sudo and no system packages. Rider bundles a complete JDK:

```text
JDK      /opt/JetBrains Rider-2026.2.0.2/jbr    javac 25.0.3
Gradle   ~/apps/gradle-8.14                     bundles Kotlin 2.0.21
```

apt's Gradle is 4.4.1 (2018) and its Kotlin is 1.3.31 (2019); neither can build a modern IntelliJ
Platform plugin. Kotlin arrives through Gradle, which is how JetBrains plugin projects are built.

## Known Faults, named at birth

- **KF-RF-1** The kotlin lane is `ungoverned`. The toolchain is live but nothing lints Kotlin.
- **KF-RF-2** No JVM job in codeforge CI, so the Rider projection is unbuilt by any gate and is
  verified only on this host.

## What RF-001A deliberately does not do

No NES decoder. That is RF-001B, Codex's order: `iNES` parsing, CHR ROM location, the 2bpp decoder,
and its byte-to-pixel tests. This scaffold gives that order its contracts and its home.
