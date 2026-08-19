// Package main runs the staged XLSX converter proof.
package main

import (
	"archive/zip"
	"bytes"
	"codeforge/sheets"
	"crypto/sha256"
	"flag"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"
)

const sheetName = "Data"

func main() {
	var sabotage string
	flag.StringVar(&sabotage, "sabotage", "", "fail one proof stage")
	flag.Parse()
	if sabotage != "" && !validStage(sabotage) {
		fmt.Fprintf(os.Stderr, "REFUSED: unknown stage %q\n", sabotage)
		os.Exit(1)
	}
	if err := run(sabotage); err != nil {
		fmt.Fprintf(os.Stderr, "REFUSED: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("VERDICT: PASS")
}

func validStage(stage string) bool {
	switch stage {
	case "synthesize", "load", "parse", "render", "integrity":
		return true
	default:
		return false
	}
}

func run(sabotage string) error {
	source, err := synthesize(sabotage)
	if err != nil {
		return err
	}
	digest := sha256.Sum256(source)
	fmt.Println("synthesize: PASS")

	filename, cleanup, err := load(source, sabotage)
	if err != nil {
		return err
	}
	defer cleanup()
	fmt.Println("load: PASS")

	cells, err := parse(filename, sabotage)
	if err != nil {
		return err
	}
	fmt.Println("parse: PASS")

	rendered, err := render(cells, sabotage)
	if err != nil {
		return err
	}
	fmt.Print(rendered)
	fmt.Println("render: PASS")

	if err := integrity(source, digest, sabotage); err != nil {
		return err
	}
	fmt.Println("integrity: PASS")
	return nil
}

func synthesize(sabotage string) ([]byte, error) {
	if sabotage == "synthesize" {
		return nil, fmt.Errorf("synthesize stage sabotaged")
	}
	var output bytes.Buffer
	archive := zip.NewWriter(&output)
	parts := []struct {
		name string
		data string
	}{
		{"[Content_Types].xml", `<?xml version="1.0"?><Types/>`},
		{"xl/workbook.xml", `<?xml version="1.0"?><workbook xmlns:r="urn:r"><sheets><sheet name="Data" r:id="rId1"/></sheets></workbook>`},
		{"xl/_rels/workbook.xml.rels", `<?xml version="1.0"?><Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>`},
		{"xl/sharedStrings.xml", `<?xml version="1.0"?><sst><si><t>shared</t></si></sst>`},
		{"xl/worksheets/sheet1.xml", `<?xml version="1.0"?><worksheet><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>hello</t></is></c><c r="B1" t="s"><v>0</v></c></row><row r="2"><c r="A2"><v>42</v></c><c r="B2" t="b"><v>1</v></c></row></sheetData></worksheet>`},
	}
	for _, part := range parts {
		writer, err := archive.Create(part.name)
		if err != nil {
			return nil, fmt.Errorf("create %s: %w", part.name, err)
		}
		if _, err := io.WriteString(writer, part.data); err != nil {
			return nil, fmt.Errorf("write %s: %w", part.name, err)
		}
	}
	if err := archive.Close(); err != nil {
		return nil, fmt.Errorf("close synthesized archive: %w", err)
	}
	return output.Bytes(), nil
}

func load(source []byte, sabotage string) (string, func(), error) {
	if sabotage == "load" {
		return "", func() {}, fmt.Errorf("load stage sabotaged")
	}
	directory, err := os.MkdirTemp("", "xlsx-slice-proof-")
	if err != nil {
		return "", func() {}, fmt.Errorf("create proof directory: %w", err)
	}
	cleanup := func() { _ = os.RemoveAll(directory) } //nolint:errcheck // cleanup is best effort.
	filename := directory + string(os.PathSeparator) + "source.xlsx"
	if err := os.WriteFile(filename, source, 0o600); err != nil {
		cleanup()
		return "", func() {}, fmt.Errorf("write source workbook: %w", err)
	}
	return filename, cleanup, nil
}

func parse(filename, sabotage string) ([]sheets.Cell, error) {
	if sabotage == "parse" {
		return nil, fmt.Errorf("parse stage sabotaged")
	}
	cells, err := sheets.ReadSheetFile(filename, sheetName)
	if err != nil {
		return nil, fmt.Errorf("parse workbook: %w", err)
	}
	return cells, nil
}

func render(cells []sheets.Cell, sabotage string) (string, error) {
	if sabotage == "render" {
		return "", fmt.Errorf("render stage sabotaged")
	}
	ordered := append([]sheets.Cell(nil), cells...)
	sort.SliceStable(ordered, func(left, right int) bool {
		if ordered[left].Row != ordered[right].Row {
			return ordered[left].Row < ordered[right].Row
		}
		return ordered[left].Column < ordered[right].Column
	})
	var output strings.Builder
	output.WriteString("SHEET Data\n")
	for _, cell := range ordered {
		fmt.Fprintf(&output, "%s | %s\n", cell.Reference, cell.Value)
	}
	return output.String(), nil
}

func integrity(source []byte, expected [32]byte, sabotage string) error {
	actual := sha256.Sum256(source)
	if sabotage == "integrity" {
		expected[0] ^= 0xff
	}
	if actual != expected {
		return fmt.Errorf("integrity check failed: source workbook changed")
	}
	return nil
}
