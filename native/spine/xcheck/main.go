// xcheck: the cross-language proof for the telemetry spine. It encodes a canonical frame to
// protobuf bytes (base64 on stdout) or decodes protobuf bytes (base64 on stdin) back to a canonical
// JSON payload. The Python parity test drives it both ways -- Go-encoded bytes must decode in Python
// and Python-encoded bytes must decode here -- proving one .proto yields byte-compatible frames in
// both languages. The canonical fixtures are duplicated, on purpose, in tests/test_telemetry.py.
package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"os"

	"google.golang.org/protobuf/proto"

	pb "codeforge/spine/telemetrypb"
)

// canonicalFrame builds the agreed fixture for a kind. These MUST match the Python test fixtures.
func canonicalFrame(kind string) (*pb.Frame, error) {
	switch kind {
	case "vitals":
		return &pb.Frame{Body: &pb.Frame_Vitals{Vitals: &pb.Vitals{
			Hp: 20, Maxhp: 40, Mp: 5, Maxmp: 10, Level: 3, Xp: 150, Nextlevel: 300,
		}}}, nil
	case "room":
		return &pb.Frame{Body: &pb.Frame_Room{Room: &pb.Room{
			Num: "forge", Name: "The Cold Forge",
			Exits: map[string]string{"north": "courtyard", "east": "tunnel"},
		}}}, nil
	case "target":
		return &pb.Frame{Body: &pb.Frame_Target{Target: &pb.Target{
			Name: "A cinder wight", Hp: 30, Maxhp: 100, Element: "flame",
			Resists: map[string]string{"stone": "Resist"},
		}}}, nil
	case "quest":
		return &pb.Frame{Body: &pb.Frame_Quest{Quest: &pb.Quest{
			Name: "Relight the Beacons", Objective: "reach Emberreach",
		}}}, nil
	default:
		return nil, fmt.Errorf("unknown kind %q", kind)
	}
}

// framePayload reconstructs a frame's payload as a plain map, mirroring parts/telemetry's *_from_pb
// (optional target fields omitted when empty), so the Python side can compare dict-to-dict.
func framePayload(f *pb.Frame) (string, map[string]any) {
	switch b := f.Body.(type) {
	case *pb.Frame_Vitals:
		v := b.Vitals
		return "vitals", map[string]any{
			"hp": v.Hp, "maxhp": v.Maxhp, "mp": v.Mp, "maxmp": v.Maxmp,
			"level": v.Level, "xp": v.Xp, "nextlevel": v.Nextlevel,
		}
	case *pb.Frame_Room:
		r := b.Room
		return "room", map[string]any{"num": r.Num, "name": r.Name, "exits": r.Exits}
	case *pb.Frame_Target:
		t := b.Target
		p := map[string]any{"name": t.Name, "hp": t.Hp, "maxhp": t.Maxhp}
		if t.Element != "" {
			p["element"] = t.Element
		}
		if len(t.Resists) > 0 {
			p["resists"] = t.Resists
		}
		return "target", p
	case *pb.Frame_Quest:
		q := b.Quest
		return "quest", map[string]any{"name": q.Name, "objective": q.Objective}
	default:
		return "", nil
	}
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: xcheck encode <kind> | xcheck decode")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "encode":
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "encode needs a kind")
			os.Exit(2)
		}
		frame, err := canonicalFrame(os.Args[2])
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		raw, err := proto.Marshal(frame)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		fmt.Println(base64.StdEncoding.EncodeToString(raw))
	case "decode":
		in, err := io.ReadAll(os.Stdin)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		raw, err := base64.StdEncoding.DecodeString(trim(string(in)))
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		frame := &pb.Frame{}
		if err := proto.Unmarshal(raw, frame); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		kind, payload := framePayload(frame)
		out, _ := json.Marshal(map[string]any{"kind": kind, "payload": payload})
		fmt.Println(string(out))
	default:
		fmt.Fprintln(os.Stderr, "unknown command:", os.Args[1])
		os.Exit(2)
	}
}

// trim drops a trailing newline from piped base64 without pulling in strings for one call.
func trim(s string) string {
	for len(s) > 0 && (s[len(s)-1] == '\n' || s[len(s)-1] == '\r') {
		s = s[:len(s)-1]
	}
	return s
}
