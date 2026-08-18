// The Go edge gateway: a transparent TCP proxy that fronts the Python gateway.
// Standard library only -- no third-party modules, so there is no go.sum to vendor.
module codeforge/edge

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
