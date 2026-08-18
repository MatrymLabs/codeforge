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
    id("org.jetbrains.intellij.platform")
    kotlin("jvm") version "2.4.0"
    // KF-RF-1: the kotlin lane opened UNGOVERNED on 2026-08-13, a live toolchain with nothing
    // inspecting it. ktlint is the instrument. It runs from the wrapper, so CI needs a JDK and
    // nothing else, and `check` depends on it so a lint failure cannot be skipped by running tests.
    id("org.jlleitschuh.gradle.ktlint") version "12.1.1"
    id("io.gitlab.arturbosch.detekt") version "1.23.8"
}

group = "labs.matrym.retroforge"
version = "0.1.0"

repositories {
    mavenCentral()
    intellijPlatform { defaultRepositories() }
}

dependencies {
    testImplementation(kotlin("test"))
    intellijPlatform { intellijIdea("2026.2") }
}

// The Kotlin lane is governed by a reproducible Java 21 toolchain. The foojay resolver in settings
// provisions the requested JDK when it is not already installed.
java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
    sourceCompatibility = JavaVersion.VERSION_21
    targetCompatibility = JavaVersion.VERSION_21
}

kotlin {
    compilerOptions { jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_21 }
}

tasks.test { useJUnitPlatform() }

detekt {
    buildUponDefaultConfig = true
    config.setFrom(files("detekt.yml"))
    baseline = file("detekt-baseline.xml")
}

tasks.named("check") {
    dependsOn("detektMain")
}

dependencies {
    detektPlugins("io.gitlab.arturbosch.detekt:detekt-formatting:1.23.8")
}

ktlint {
    version.set("1.3.1")
    // A warning nobody has to act on is decoration. A lint finding fails this build.
    ignoreFailures.set(false)
    reporters {
        reporter(org.jlleitschuh.gradle.ktlint.reporter.ReporterType.PLAIN)
    }
}
