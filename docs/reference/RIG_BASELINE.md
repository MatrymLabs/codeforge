# RIG BASELINE — RDY ELEMENT HYBRID MAX II
## The Windows baseline tailored to THIS machine, with the omnicode mandate written in.

**This supersedes the generic parts of the Windows PC Baseline reference with rig-specific
rulings, and installs the omnicode mandate the reference omitted. Companion documents:
the Windows PC Baseline reference (general layer) and the Omni-Stack Practices Reference
(per-language layer). This file is the machine layer.**

---

## 1. THE RIG, READ AS A DEV MACHINE

| Part | Spec | What it means for the Workshop |
|---|---|---|
| CPU | i9-13900KF: 8 P-cores + 16 E-cores (24 cores / 32 threads) | Massive parallel build/test capacity, but HYBRID: P-cores and E-cores differ, which affects parallelism tuning (below) |
| RAM | 32GB DDR5-6000 | **The real constraint on this rig.** Fine for normal work; caps how many heavy parallel builds + Rider + agents + local LLM runtime coexist. Rules below |
| GPU | RTX 4090 SUPRIM LIQUID 24GB | Local LLM inference (a 32B coding model fits in VRAM), Godot rendering, NVENC for NoMachine. Does nothing for builds/tests |
| Storage | 2TB Samsung PRO Gen4 NVMe | Fast enough that a RAM disk is unnecessary. Watch capacity: Rust target/, node_modules, model weights, and 13 repos add up |
| Board | ASUS ROG STRIX Z790-E | BIOS updates matter here (see the one hardware warning below) |
| OS | **Windows 11 Home** | No RDP hosting, no Group Policy. NoMachine + Tailscale is the remote path (already the plan). Everything else in the baseline works on Home |
| CPU cooling | 280mm AIO | Sustained all-core builds are fine thermally |
| KF SKU | No integrated GPU | Display and NVENC both run on the 4090; if the 4090 is ever pulled, the machine has no video |

## 2. THE ONE HARDWARE WARNING (do this before heavy building)

The i9-13900K-family (Raptor Lake) had a documented instability/degradation issue tied to
elevated voltage, fixed by Intel microcode delivered through BIOS updates. An out-of-date
BIOS on this Z790-E risks slow CPU degradation under exactly the sustained all-core load
the Workshop will now generate.

**Action, first session:** update the ASUS Z790-E BIOS to the latest version (includes the
Intel microcode mitigations), and use Intel Default power settings in BIOS rather than
motherboard "unlimited" defaults. Fifteen minutes, protects the CPU. UNVERIFIED whether
this unit already shipped patched: check the BIOS version and confirm, do not assume.

## 3. PARALLELISM TUNED TO THE 13900KF (hybrid-aware)

24 physical cores, but 8 fast P-cores + 16 efficient E-cores. Windows 11's scheduler
handles placement, but job counts should reflect reality:

- **pytest:** `-n auto` (counts physical cores = 24). If workers starve RAM (see rule
  below), pin lower: `-n 16`.
- **cargo:** default uses all threads. With 32GB, cap during heavy link-stage crates:
  `CARGO_BUILD_JOBS=16` if you see swapping; otherwise leave default.
- **Gradle:** `org.gradle.parallel=true`, `org.gradle.caching=true`,
  `org.gradle.workers.max=8` (JVM workers are RAM-heavy; 8 on 32GB is the safe ceiling).
- **Go:** defaults fine (GOMAXPROCS=32).
- **golangci-lint:** default concurrency fine.

**The 32GB rule:** Rider (~2-4GB) + two agent terminals + one full parallel build fits.
Two simultaneous heavy builds (cargo link + Gradle) plus Rider can swap. Sequence heavy
builds rather than stacking them, or cap jobs as above. If the Workshop's parallel load
grows, the single highest-value hardware upgrade for this rig is 32GB -> 64GB (two DIMM
slots are free on the Z790-E); until then, the caps are the fix.

**Local LLM note:** a 32B Q4 model lives in the 4090's 24GB VRAM, not system RAM, so it
coexists with builds. But Ollama's runtime plus context still takes system RAM; close it
during maximum-parallelism build sessions if memory gets tight.

## 4. WINDOWS 11 HOME SPECIFICS

- **Remote:** no RDP hosting on Home. NoMachine (NVENC on the 4090) over Tailscale,
  bound to the Tailscale interface, no forwarded ports. This was already the plan; Home
  makes it the only plan.
- **Defender exclusions, long paths, Developer Mode, symlinks, fsmonitor:** all work on
  Home exactly as the baseline reference specifies. No Group Policy needed; everything is
  done via PowerShell/registry as written.
- **Sleep:** `powercfg /change standby-timeout-ac 0` — mandatory, or NoMachine sessions
  die and porch access breaks.

## 5. THE OMNICODE MANDATE (the missing section, now law at the machine layer)

The baseline reference described the current languages. It did not state the mandate.
Stated now:

**Part A — Capability is total on this rig.** Every language Rider supports is a
first-class Workshop language, and this machine is provisioned so ANY of them can be
installed and gated ON DEMAND, same-day, without research or friction. The machine layer
guarantees: Rider (the omni IDE) installed; winget + the pinned bootstrap config as the
universal install surface; the Taskfile as the universal gate surface with per-language
targets; Defender/long-path/line-ending config that is language-agnostic. No Target
Product language is ever refused because the machine cannot host it.

**Part B — Toolchain and gate arrive with the rung.** Nothing is pre-installed for
languages with no code in the tree. When a Blueprint's Target Product brings a new
language: (1) install its canonical toolchain via winget/scoop, version pinned, added to
the bootstrap config the same day; (2) wire its lint/typecheck/test/security targets into
the Taskfile; (3) calibrate each target red-then-green before trusting it; (4) add its
Fittings path in the Hardware Store. The gate never reports green over a language it
cannot inspect — capability is unlimited, but PRESENT status is earned per language.

**The install surface, ready today** (deferred until each rung, IDs verified in the
baseline research): Python (uv), Rust (rustup), Go, JDK (Temurin + Gradle toolchains),
Node (fnm), GDScript (Godot + gdtoolkit via uv), TypeScript (pnpm via fnm's Node), C#
(.NET SDK via winget), C++ (VS Build Tools + CMake via winget). One `winget configure`
against the bootstrap file provisions any of them on demand. That file IS the omnicode
mandate made mechanical: the machine can always say yes to a new language, immediately,
reproducibly, pinned.

## 6. DO-THIS-FIRST ON THIS RIG (ordered)

1. BIOS check/update + Intel Default power profile (section 2). Before heavy building.
2. Defender exclusions, long paths + reboot, .gitattributes + renormalize, fsmonitor +
   untrackedcache, Developer Mode + core.symlinks, sleep off (per the baseline reference,
   all Home-compatible).
3. Confirm C:\Projects\MatrymLabs is outside OneDrive.
4. Parallelism flags per section 3 (pytest addopts, gradle.properties, know the cargo cap).
5. Tailscale on PC + Pi; bind NoMachine to it.
6. Write the winget DSC bootstrap file into a machine-bootstrap repo with the currently
   present languages; structure it so a new language is a one-block, one-command add.
   This file is the omnicode mandate's physical form.
7. Gradle toolchain + foojay pin to JDK 21 for RetroForge (kills the 21/24 mismatch).
8. Makefile -> Taskfile migration when convenient (the gate surface for all languages).

---

The machine layer in one line: a 24-core hybrid CPU tuned with RAM-aware caps, a 4090
reserved for models and Godot, Home-edition remote via NoMachine over Tailscale, one BIOS
warning handled first, and a bootstrap file that makes every language Rider supports
installable on sight — capability total, toolchain with the rung, gate with the toolchain.

Build around the rig. The rig can say yes to any language. Go.
