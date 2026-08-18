// The Go end of the telemetry spine: the generated binding (telemetrypb, git-ignored, rebuilt via
// `make proto`) plus a tiny cross-language check CLI (xcheck). One third-party dependency, the
// protobuf runtime -- pinned here and in go.sum for reproducibility.
module codeforge/spine

go 1.26.5

require google.golang.org/protobuf v1.34.2
