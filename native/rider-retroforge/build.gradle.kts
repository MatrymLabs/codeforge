// The Rider projection for RetroForge.
//
// This build is deliberately PLAIN Kotlin/JVM, not the IntelliJ Platform plugin build, and that is
// a decision rather than an omission. The platform plugin downloads a multi-gigabyte SDK on first
// configure; skynet is a Pi 5 at 85% disk. RF-001A proves the toolchain and the seam, and the
// platform dependency arrives with the Work Order that actually needs an editor, which is the
// same rule doctrine applies to every toolchain: it comes with the rung that needs it.
//
// What this build DOES prove: Kotlin compiles here, tests run here, and the projection can be
// gated. That is the property RF-001A owes.

plugins {
    kotlin("jvm") version "2.2.0"
    // KF-RF-1: the kotlin lane opened UNGOVERNED on 2026-08-13, a live toolchain with nothing
    // inspecting it. ktlint is the instrument. It runs from the wrapper, so CI needs a JDK and
    // nothing else, and `check` depends on it so a lint failure cannot be skipped by running tests.
    id("org.jlleitschuh.gradle.ktlint") version "12.1.1"
}

group = "labs.matrym.retroforge"
version = "0.1.0"

repositories { mavenCentral() }

dependencies {
    testImplementation(kotlin("test"))
}

// Bytecode is pinned at 24, which is the highest Kotlin 2.2.0 emits, while compiling ON JBR 25.
// Left unpinned, javac targeted 25 and kotlinc targeted 24 and Gradle refused the mismatch. It was
// right to: two halves of one artifact compiled for different JVMs is the kind of thing that runs
// fine until the one class that does not.
java {
    sourceCompatibility = JavaVersion.VERSION_24
    targetCompatibility = JavaVersion.VERSION_24
}

kotlin {
    compilerOptions { jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_24 }
}

// NO jvmToolchain() pin, deliberately. This is a RIDER projection, so its runtime should follow
// the JBR Rider actually ships: today JBR 25.0.3, and the only JDK on this host. A pinned 21 was
// the first thing written here and it failed exactly as it should have, with Gradle refusing to
// invent a toolchain it could not find. Pinning a version the IDE does not ship would mean either
// downloading a second JDK to satisfy a number, or a build that breaks whenever Rider updates.

tasks.test { useJUnitPlatform() }

ktlint {
    version.set("1.3.1")
    // A warning nobody has to act on is decoration. A lint finding fails this build.
    ignoreFailures.set(false)
    reporters {
        reporter(org.jlleitschuh.gradle.ktlint.reporter.ReporterType.PLAIN)
    }
}
