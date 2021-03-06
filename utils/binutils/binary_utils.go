package glyph

import (
	"fmt"
	glyph "glyph/glyph/utils"
	"os"
)

//FunctionDetails A struct storing details for a single function.
type FunctionDetails struct {
	FunctionName   string   `json:"functionName"`
	ReturnType     string   `json:"returnType"`
	ParameterCount int      `json:"parameterCount"`
	LowAddress     string   `json:"lowAddress"`
	HighAddress    string   `json:"highAddress"`
	Tokens         []string `json:"tokenList"`
}

type erroredFunctionDetails struct {
	LowAddress  string   `json:"lowAddress"`
	HighAddress string   `json:"highAddress"`
	Tokens      []string `json:"tokenList"`
}

//BinaryDetails A structure of details about an analyzed binary.
type BinaryDetails struct {
	BinaryName   string `json:"binaryName"`
	FunctionsMap struct {
		FunctionDetails         []FunctionDetails        `json:"functions"`
		ErroredFunctionsDetails []erroredFunctionDetails `json:"erroredFunctions"`
	} `json:"functionsMap"`
}

//CheckIfElf Determines if a binary file is an ELF file.
func CheckIfElf(file *os.File) bool {
	f := glyph.IOReader(file.Name())
	var ident [16]uint8
	_, err := f.ReadAt(ident[0:], 0)
	if err != nil {
		return false
	} else if ident[0] != '\x7f' || ident[1] != 'E' || ident[2] != 'L' || ident[3] != 'F' {
		fmt.Printf("Bad magic number at %d\n", ident[0:4])
		return false
	}
	return true
}
