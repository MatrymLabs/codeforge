// Round-trip tests for the Go telemetry binding: every canonical frame survives a
// Marshal -> Unmarshal cycle unchanged, and the oneof body is recovered correctly. Proves the Go
// side of the spine works; cross-language agreement with Python is proven by xcheck + the Python
// parity test.
package main

import (
	"testing"

	"google.golang.org/protobuf/proto"

	pb "codeforge/spine/telemetrypb"
)

func roundTrip(t *testing.T, frame *pb.Frame) *pb.Frame {
	t.Helper()
	raw, err := proto.Marshal(frame)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	got := &pb.Frame{}
	if err := proto.Unmarshal(raw, got); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	return got
}

func TestVitalsRoundTrips(t *testing.T) {
	in := &pb.Frame{Body: &pb.Frame_Vitals{Vitals: &pb.Vitals{Hp: 20, Maxhp: 40, Level: 3, Nextlevel: -1}}}
	got := roundTrip(t, in)
	v := got.GetVitals()
	if v == nil {
		t.Fatal("body is not vitals")
	}
	if v.Hp != 20 || v.Maxhp != 40 || v.Level != 3 || v.Nextlevel != -1 {
		t.Fatalf("vitals mismatch: %+v", v)
	}
}

func TestRoomRoundTripsWithExits(t *testing.T) {
	in := &pb.Frame{Body: &pb.Frame_Room{Room: &pb.Room{
		Num: "forge", Name: "The Cold Forge",
		Exits: map[string]string{"north": "courtyard", "east": "tunnel"},
	}}}
	r := roundTrip(t, in).GetRoom()
	if r == nil || r.Num != "forge" || r.Exits["north"] != "courtyard" || len(r.Exits) != 2 {
		t.Fatalf("room mismatch: %+v", r)
	}
}

func TestTargetOptionalFields(t *testing.T) {
	// A typed foe keeps its element + resists...
	typed := roundTrip(t, &pb.Frame{Body: &pb.Frame_Target{Target: &pb.Target{
		Name: "A cinder wight", Hp: 30, Maxhp: 100, Element: "flame",
		Resists: map[string]string{"stone": "Resist"},
	}}}).GetTarget()
	if typed.Element != "flame" || typed.Resists["stone"] != "Resist" {
		t.Fatalf("typed target lost its profile: %+v", typed)
	}
	// ...an untyped foe carries neither (the zero value, which the payload rules omit).
	plain := roundTrip(t, &pb.Frame{Body: &pb.Frame_Target{Target: &pb.Target{
		Name: "a training dummy", Hp: 50, Maxhp: 50,
	}}}).GetTarget()
	if plain.Element != "" || len(plain.Resists) != 0 {
		t.Fatalf("untyped target invented a profile: %+v", plain)
	}
}

func TestQuestRoundTrips(t *testing.T) {
	q := roundTrip(t, &pb.Frame{Body: &pb.Frame_Quest{Quest: &pb.Quest{
		Name: "Relight the Beacons", Objective: "reach Emberreach",
	}}}).GetQuest()
	if q == nil || q.Name != "Relight the Beacons" || q.Objective != "reach Emberreach" {
		t.Fatalf("quest mismatch: %+v", q)
	}
}
