// The Go end of the telemetry spine: the generated binding (telemetrypb, git-ignored, rebuilt via
// `make proto`) plus a tiny cross-language check CLI (xcheck). One third-party dependency, the
// protobuf runtime -- pinned here and in go.sum for reproducibility.
module codeforge/spine

// GO DIRECTIVE = MINIMUM LANGUAGE VERSION, NOT THE TOOLCHAIN. The two were conflated on
// 2026-08-18 and CI caught it: setting this to 1.26.5 made golangci-lint refuse the module
// outright, because the linter is itself built with go1.25 and cannot analyse a target above
// its own build version:
//
//   can't load config: the Go language version (go1.25) used to build golangci-lint is
//   lower than the targeted Go version (1.26.5)
//
// The bench did not reproduce it; only CI did. So this stays a FLOOR that the tooling can
// handle, while the toolchain that actually compiles and scans is pinned in ci.yml at 1.26.5,
// above the 1.26.3 security floor for GO-2026-4971. Two numbers, two meanings, on purpose.
go 1.25

require google.golang.org/protobuf v1.34.2
