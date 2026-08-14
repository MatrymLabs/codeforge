# rider-retroforge

The Rider projection for RetroForge. **It owns no decoding.**

`kernel/retroforge/` decides what the bytes mean. This draws the answer. Every format question
belongs on the other side of that line, and the moment a tile layout is described in this
directory the layering has failed.

## Build

No sudo, no system packages:

```bash
export JAVA_HOME="/opt/JetBrains Rider-2026.2.0.2/jbr"   # Rider bundles a full JDK
~/apps/gradle-9.1.0/bin/gradle build                       # or ./gradlew once wrapped
```

apt's Gradle is 4.4.1 (2018) and its Kotlin is 1.3.31 (2019). Neither can build a modern IntelliJ
Platform plugin, so Kotlin arrives through Gradle instead, which is how JetBrains plugin projects
are built anyway.

## Why this is not yet an IntelliJ Platform plugin

The platform plugin pulls a multi-gigabyte SDK on first configure and this host is a Pi 5 at 85%
disk. RF-001A owes proof that the toolchain works and the seam holds, not an editor. The platform
dependency arrives with the Work Order that needs an editor.

## Known Faults

- **KF-RF-1** the kotlin lane is `ungoverned`: no linter inspects Kotlin yet.
- **KF-RF-2** no JVM job in codeforge CI, so this is verified only on skynet.
