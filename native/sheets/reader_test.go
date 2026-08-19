package sheets

import (
	"archive/zip"
	"bytes"
	"encoding/binary"
	"errors"
	"testing"
)

func testWorkbook(t *testing.T) []byte {
	t.Helper()
	var output bytes.Buffer
	archive := zip.NewWriter(&output)
	parts := map[string]string{
		"[Content_Types].xml":        `<?xml version="1.0"?><Types/>`,
		"xl/workbook.xml":            `<?xml version="1.0"?><workbook xmlns:r="urn:r"><sheets><sheet name="Data" r:id="rId1"/></sheets></workbook>`,
		"xl/_rels/workbook.xml.rels": `<?xml version="1.0"?><Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>`,
		"xl/sharedStrings.xml":       `<?xml version="1.0"?><sst><si><t>shared</t></si></sst>`,
		"xl/worksheets/sheet1.xml":   `<?xml version="1.0"?><worksheet><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>hello</t></is></c><c r="B1" t="s"><v>0</v></c></row><row r="2"><c r="A2"><v>42</v></c><c r="B2" t="b"><v>1</v></c></row></sheetData></worksheet>`,
	}
	for name, contents := range parts {
		writer, err := archive.Create(name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := writer.Write([]byte(contents)); err != nil {
			t.Fatal(err)
		}
	}
	if err := archive.Close(); err != nil {
		t.Fatal(err)
	}
	return output.Bytes()
}

func TestReadSheetReturnsNamedCells(t *testing.T) {
	cells, err := ReadSheet(testWorkbook(t), "Data")
	if err != nil {
		t.Fatal(err)
	}
	want := []Cell{
		{Reference: "A1", Row: 0, Column: 0, Value: "hello"},
		{Reference: "B1", Row: 0, Column: 1, Value: "shared"},
		{Reference: "A2", Row: 1, Column: 0, Value: "42"},
		{Reference: "B2", Row: 1, Column: 1, Value: "TRUE"},
	}
	if len(cells) != len(want) {
		t.Fatalf("got %d cells, want %d: %#v", len(cells), len(want), cells)
	}
	for index := range want {
		if cells[index] != want[index] {
			t.Errorf("cell %d = %#v, want %#v", index, cells[index], want[index])
		}
	}
}

func TestReadSheetRefusesMissingSheet(t *testing.T) {
	_, err := ReadSheet(testWorkbook(t), "Missing")
	if !errors.Is(err, ErrSheetNotFound) {
		t.Fatalf("error = %v, want ErrSheetNotFound", err)
	}
}

func TestHostileXLSXInputsFailCleanly(t *testing.T) {
	tests := []struct { //nolint:govet // table readability is more useful than field packing here.
		name string
		data []byte
		want error
	}{
		{name: "truncated archive", data: testWorkbook(t)[:len(testWorkbook(t))-3], want: ErrInvalidArchive},
		{name: "garbage bytes", data: []byte("not a zip archive"), want: ErrInvalidArchive},
		{name: "declared size lie", data: declaredSizeLie(t), want: ErrArchiveTooLarge},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			defer func() {
				if recovered := recover(); recovered != nil {
					t.Fatalf("parser panicked on hostile input: %v", recovered)
				}
			}()
			_, err := ReadSheet(test.data, "Data")
			if !errors.Is(err, test.want) {
				t.Fatalf("error = %v, want %v", err, test.want)
			}
		})
	}
}

func declaredSizeLie(t *testing.T) []byte {
	t.Helper()
	data := append([]byte(nil), testWorkbook(t)...)
	centralDirectory := bytes.Index(data, []byte("PK\x01\x02"))
	if centralDirectory < 0 {
		t.Fatal("test workbook has no central directory")
	}
	// ZIP32 stores the uncompressed-size field 24 bytes after the central-directory signature.
	binary.LittleEndian.PutUint32(data[centralDirectory+24:], uint32(MaxMemberUncompressedBytes+1))
	return data
}
