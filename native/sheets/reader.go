// Package sheets reads the small, stable subset of XLSX needed by the converter.
//
// An XLSX file is a ZIP archive of XML parts. The reader never extracts a member to disk and
// applies byte limits before opening or decompressing any member. It is therefore a parser for
// untrusted binary input, not a general-purpose spreadsheet runtime.
package sheets

import (
	"archive/zip"
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"os"
	pathpkg "path"
	"strconv"
	"strings"
)

const (
	// MaxWorkbookBytes bounds a workbook supplied through a file or reader.
	MaxWorkbookBytes int64 = 64 << 20
	// MaxMemberUncompressedBytes prevents a ZIP member from expanding without bound.
	MaxMemberUncompressedBytes uint64 = 32 << 20
	// MaxTotalUncompressedBytes bounds the sum of declared member sizes.
	MaxTotalUncompressedBytes uint64 = 128 << 20
	// maxXMLNestingDepth bounds recursive XML structure inside a workbook member.
	maxXMLNestingDepth = 10000
)

var (
	// ErrInvalidArchive means the input is not a readable ZIP archive.
	ErrInvalidArchive = errors.New("invalid XLSX archive")
	// ErrArchiveTooLarge means a workbook or member exceeds a safety limit.
	ErrArchiveTooLarge = errors.New("XLSX archive exceeds safety limit")
	// ErrArchiveTruncated means a member's declared size does not match its data.
	ErrArchiveTruncated = errors.New("XLSX archive is truncated")
	// ErrInvalidXML means a required XML part is malformed or unsafe.
	ErrInvalidXML = errors.New("invalid XLSX XML")
	// ErrSheetNotFound means the requested worksheet name is absent.
	ErrSheetNotFound = errors.New("XLSX sheet not found")
)

// Cell is one populated cell in a worksheet. Row and Column are zero-based.
type Cell struct {
	Reference string
	Value     string
	Row       int
	Column    int
}

type workbookSheet struct {
	Name  string
	RelID string
}

type relationship struct {
	ID       string
	Target   string
	External bool
}

// ReadSheet reads one named worksheet from an XLSX byte sequence.
func ReadSheet(data []byte, sheetName string) ([]Cell, error) {
	if int64(len(data)) > MaxWorkbookBytes {
		return nil, fmt.Errorf("%w: workbook is %d bytes, limit is %d", ErrArchiveTooLarge, len(data), MaxWorkbookBytes)
	}
	archive, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return nil, fmt.Errorf("%w: %w", ErrInvalidArchive, err)
	}
	return readArchive(archive, sheetName)
}

// ReadSheetFile reads one named worksheet from a bounded XLSX file.
func ReadSheetFile(filename, sheetName string) ([]Cell, error) {
	file, err := os.Open(filename) //nolint:gosec // callers choose the workbook path explicitly.
	if err != nil {
		return nil, fmt.Errorf("open XLSX: %w", err)
	}
	defer func() {
		if closeErr := file.Close(); closeErr != nil {
			return
		}
	}()
	data, err := io.ReadAll(io.LimitReader(file, MaxWorkbookBytes+1))
	if err != nil {
		return nil, fmt.Errorf("read XLSX: %w", err)
	}
	return ReadSheet(data, sheetName)
}

func readArchive(archive *zip.Reader, sheetName string) ([]Cell, error) {
	parts := make(map[string]*zip.File, len(archive.File))
	var declaredTotal uint64
	for _, member := range archive.File {
		if _, exists := parts[member.Name]; exists {
			return nil, fmt.Errorf("%w: duplicate member %q", ErrInvalidArchive, member.Name)
		}
		if member.UncompressedSize64 > MaxMemberUncompressedBytes {
			return nil, fmt.Errorf("%w: member %q declares %d bytes", ErrArchiveTooLarge, member.Name, member.UncompressedSize64)
		}
		if member.UncompressedSize64 > MaxTotalUncompressedBytes-declaredTotal {
			return nil, fmt.Errorf("%w: declared members exceed %d bytes", ErrArchiveTooLarge, MaxTotalUncompressedBytes)
		}
		declaredTotal += member.UncompressedSize64
		parts[member.Name] = member
	}

	workbook, ok := parts["xl/workbook.xml"]
	if !ok {
		return nil, fmt.Errorf("%w: xl/workbook.xml is missing", ErrInvalidXML)
	}
	workbookData, err := readMember(workbook)
	if err != nil {
		return nil, err
	}
	sheets, err := parseWorkbook(workbookData)
	if err != nil {
		return nil, err
	}
	selected, ok := findSheet(sheets, sheetName)
	if !ok {
		return nil, fmt.Errorf("%w: %q", ErrSheetNotFound, sheetName)
	}

	rels, ok := parts["xl/_rels/workbook.xml.rels"]
	if !ok {
		return nil, fmt.Errorf("%w: workbook relationships are missing", ErrInvalidXML)
	}
	relData, err := readMember(rels)
	if err != nil {
		return nil, err
	}
	relationships, err := parseRelationships(relData)
	if err != nil {
		return nil, err
	}
	rel, ok := relationships[selected.RelID]
	if !ok || rel.External {
		return nil, fmt.Errorf("%w: relationship %q is unavailable", ErrInvalidXML, selected.RelID)
	}
	sheetPath, err := resolveSheetPath(rel.Target)
	if err != nil {
		return nil, err
	}
	sheet, ok := parts[sheetPath]
	if !ok {
		return nil, fmt.Errorf("%w: worksheet %q is missing", ErrInvalidXML, sheetPath)
	}
	sheetData, err := readMember(sheet)
	if err != nil {
		return nil, err
	}
	sharedStrings, err := readSharedStrings(parts)
	if err != nil {
		return nil, err
	}
	return parseWorksheet(sheetData, sharedStrings)
}

func readMember(member *zip.File) ([]byte, error) {
	if member.UncompressedSize64 > MaxMemberUncompressedBytes {
		return nil, fmt.Errorf("%w: member %q declares %d bytes", ErrArchiveTooLarge, member.Name, member.UncompressedSize64)
	}
	reader, err := member.Open()
	if err != nil {
		return nil, fmt.Errorf("%w: open member %q: %w", ErrInvalidArchive, member.Name, err)
	}
	defer func() {
		if closeErr := reader.Close(); closeErr != nil {
			return
		}
	}()
	data, err := io.ReadAll(io.LimitReader(reader, int64(MaxMemberUncompressedBytes)+1))
	if err != nil {
		return nil, fmt.Errorf("%w: read member %q: %w", ErrInvalidArchive, member.Name, err)
	}
	if uint64(len(data)) > MaxMemberUncompressedBytes {
		return nil, fmt.Errorf("%w: member %q expanded beyond the limit", ErrArchiveTooLarge, member.Name)
	}
	if uint64(len(data)) != member.UncompressedSize64 {
		return nil, fmt.Errorf("%w: member %q declares %d bytes but yielded %d", ErrArchiveTruncated, member.Name, member.UncompressedSize64, len(data))
	}
	return data, nil
}

func parseWorkbook(data []byte) ([]workbookSheet, error) {
	decoder := xml.NewDecoder(bytes.NewReader(data))
	var result []workbookSheet
	for {
		token, err := decoder.Token()
		if errors.Is(err, io.EOF) {
			return result, nil
		}
		if err != nil {
			return nil, fmt.Errorf("%w: workbook.xml: %w", ErrInvalidXML, err)
		}
		start, ok := token.(xml.StartElement)
		if !ok || start.Name.Local != "sheet" {
			continue
		}
		var sheet workbookSheet
		for _, attr := range start.Attr {
			switch attr.Name.Local {
			case "name":
				sheet.Name = attr.Value
			case "id":
				sheet.RelID = attr.Value
			}
		}
		if sheet.Name == "" || sheet.RelID == "" {
			return nil, fmt.Errorf("%w: sheet has no name or relationship id", ErrInvalidXML)
		}
		result = append(result, sheet)
	}
}

func parseRelationships(data []byte) (map[string]relationship, error) {
	decoder := xml.NewDecoder(bytes.NewReader(data))
	result := make(map[string]relationship)
	for {
		token, err := decoder.Token()
		if errors.Is(err, io.EOF) {
			return result, nil
		}
		if err != nil {
			return nil, fmt.Errorf("%w: workbook relationships: %w", ErrInvalidXML, err)
		}
		start, ok := token.(xml.StartElement)
		if !ok || start.Name.Local != "Relationship" {
			continue
		}
		var rel relationship
		for _, attr := range start.Attr {
			switch attr.Name.Local {
			case "Id":
				rel.ID = attr.Value
			case "Target":
				rel.Target = attr.Value
			case "TargetMode":
				rel.External = strings.EqualFold(attr.Value, "External")
			}
		}
		if rel.ID == "" || rel.Target == "" {
			return nil, fmt.Errorf("%w: relationship is missing Id or Target", ErrInvalidXML)
		}
		if _, exists := result[rel.ID]; exists {
			return nil, fmt.Errorf("%w: duplicate relationship %q", ErrInvalidXML, rel.ID)
		}
		result[rel.ID] = rel
	}
}

func findSheet(sheets []workbookSheet, name string) (workbookSheet, bool) {
	for _, sheet := range sheets {
		if sheet.Name == name {
			return sheet, true
		}
	}
	return workbookSheet{}, false
}

func resolveSheetPath(target string) (string, error) {
	target = strings.ReplaceAll(target, "\\", "/")
	if strings.HasPrefix(target, "/") {
		target = strings.TrimPrefix(target, "/")
	} else {
		target = pathpkg.Join("xl", target)
	}
	clean := pathpkg.Clean(target)
	if clean == "." || clean == ".." || strings.HasPrefix(clean, "../") || !strings.HasPrefix(clean, "xl/") {
		return "", fmt.Errorf("%w: worksheet target %q escapes xl", ErrInvalidXML, target)
	}
	return clean, nil
}

func readSharedStrings(parts map[string]*zip.File) ([]string, error) {
	member, ok := parts["xl/sharedStrings.xml"]
	if !ok {
		return nil, nil
	}
	data, err := readMember(member)
	if err != nil {
		return nil, err
	}
	decoder := xml.NewDecoder(bytes.NewReader(data))
	var result []string
	var current strings.Builder
	insideItem := false
	for {
		token, err := decoder.Token()
		if errors.Is(err, io.EOF) {
			return result, nil
		}
		if err != nil {
			return nil, fmt.Errorf("%w: sharedStrings.xml: %w", ErrInvalidXML, err)
		}
		switch value := token.(type) {
		case xml.StartElement:
			if value.Name.Local == "si" {
				insideItem = true
				current.Reset()
			}
		case xml.CharData:
			if insideItem {
				current.Write([]byte(value))
			}
		case xml.EndElement:
			if value.Name.Local == "si" && insideItem {
				result = append(result, current.String())
				insideItem = false
			}
		}
	}
}

func parseWorksheet(data []byte, sharedStrings []string) ([]Cell, error) {
	decoder := xml.NewDecoder(bytes.NewReader(data))
	var result []Cell
	for {
		token, err := decoder.Token()
		if errors.Is(err, io.EOF) {
			return result, nil
		}
		if err != nil {
			return nil, fmt.Errorf("%w: worksheet: %w", ErrInvalidXML, err)
		}
		start, ok := token.(xml.StartElement)
		if !ok || start.Name.Local != "c" {
			continue
		}
		cell, err := parseCell(decoder, start, sharedStrings)
		if err != nil {
			return nil, err
		}
		result = append(result, cell)
	}
}

func parseCell(decoder *xml.Decoder, start xml.StartElement, sharedStrings []string) (Cell, error) {
	var reference, cellType string
	for _, attr := range start.Attr {
		switch attr.Name.Local {
		case "r":
			reference = attr.Value
		case "t":
			cellType = attr.Value
		}
	}
	if reference == "" {
		return Cell{}, fmt.Errorf("%w: cell has no reference", ErrInvalidXML)
	}
	row, column, err := parseReference(reference)
	if err != nil {
		return Cell{}, err
	}
	var value string
	depth := 1
	for depth > 0 {
		token, err := decoder.Token()
		if err != nil {
			return Cell{}, fmt.Errorf("%w: cell %s: %w", ErrInvalidXML, reference, err)
		}
		switch item := token.(type) {
		case xml.StartElement:
			depth++
			if depth > maxXMLNestingDepth {
				return Cell{}, fmt.Errorf("%w: cell %s exceeds XML nesting limit %d", ErrInvalidXML, reference, maxXMLNestingDepth)
			}
			if item.Name.Local == "v" || (cellType == "inlineStr" && item.Name.Local == "t") {
				text, err := readElementText(decoder, item)
				if err != nil {
					return Cell{}, fmt.Errorf("%w: cell %s value: %w", ErrInvalidXML, reference, err)
				}
				value = text
				depth--
			}
		case xml.EndElement:
			depth--
		}
	}
	if cellType == "s" {
		index, err := strconv.Atoi(value)
		if err != nil || index < 0 || index >= len(sharedStrings) {
			return Cell{}, fmt.Errorf("%w: shared string index %q in cell %s", ErrInvalidXML, value, reference)
		}
		value = sharedStrings[index]
	}
	if cellType == "b" {
		switch value {
		case "0":
			value = "FALSE"
		case "1":
			value = "TRUE"
		}
	}
	return Cell{Reference: reference, Row: row, Column: column, Value: value}, nil
}

func readElementText(decoder *xml.Decoder, start xml.StartElement) (string, error) {
	depth := 1
	var text strings.Builder
	for depth > 0 {
		token, err := decoder.Token()
		if err != nil {
			return "", err
		}
		switch item := token.(type) {
		case xml.StartElement:
			depth++
			if depth > maxXMLNestingDepth {
				return "", fmt.Errorf("XML element %q exceeds nesting limit %d", start.Name.Local, maxXMLNestingDepth)
			}
		case xml.CharData:
			text.Write([]byte(item))
		case xml.EndElement:
			depth--
		}
	}
	return text.String(), nil
}

func parseReference(reference string) (int, int, error) {
	cut := 0
	for cut < len(reference) && reference[cut] >= 'A' && reference[cut] <= 'Z' {
		cut++
	}
	if cut == 0 || cut == len(reference) {
		return 0, 0, fmt.Errorf("%w: invalid cell reference %q", ErrInvalidXML, reference)
	}
	column := 0
	for _, char := range reference[:cut] {
		column = column*26 + int(char-'A'+1)
	}
	row, err := strconv.Atoi(reference[cut:])
	if err != nil || row < 1 {
		return 0, 0, fmt.Errorf("%w: invalid cell reference %q", ErrInvalidXML, reference)
	}
	return row - 1, column - 1, nil
}
