package elftools

import (
	"debug/elf"
	"errors"
	"fmt"
	"glyph/glyph/util"
	"os"
)

//CheckIfElf Determines if a binary file is an ELF file.
func CheckIfElf(file *os.File) bool {
	f := util.IOReader(file.Name())
	var ident [16]uint8
	_, err := f.ReadAt(ident[0:], 0)
	util.CheckError(err)

	if ident[0] != '\x7f' || ident[1] != 'E' || ident[2] != 'L' || ident[3] != 'F' {
		fmt.Printf("Bad magic number at %d\n", ident[0:4])
		return false
	}
	return true
}

//GetTextSection Obtains the .text section of an ELF binary and returns a pointer to it.
func GetTextSection(filename string) (*[]byte, error) {
	var data []byte

	if !util.CheckIfFileExist(filename) {
		error := errors.New("File does not exist")
		return nil, error
	}

	f := util.IOReader(filename)
	elfFile, err := elf.NewFile(f)
	util.CheckError(err)

	var sections = elfFile.Sections

	for _, section := range sections {
		if section.Name == ".text" {
			data, _ = section.Data()
		}
	}
	return &data, nil
}
