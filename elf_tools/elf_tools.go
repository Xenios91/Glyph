package elf_tools

import (
	"debug/elf"
	"errors"
	"fmt"
	"glyph/glyph/util"
	"io"
	"os"
)

func check(err error) {
	if err != nil {
		panic(err)
	}
}

func ioReader(file string) io.ReaderAt {
	reader, err := os.Open(file)
	check(err)
	return reader
}

func GetTextSection(filename string) ([]byte, error) {
	var data []byte

	if !util.CheckIfFileExist(filename) {
		error := errors.New("File does not exist")
		return nil, error
	}

	f := ioReader(filename)
	elfFile, err := elf.NewFile(f)
	check(err)

	// Read and decode ELF identifier
	var ident [16]uint8
	f.ReadAt(ident[0:], 0)
	check(err)

	//make sure binary is an elf file
	if ident[0] != '\x7f' || ident[1] != 'E' || ident[2] != 'L' || ident[3] != 'F' {
		fmt.Printf("Bad magic number at %d\n", ident[0:4])
		panic("invalid binary")
	}

	var sections = elfFile.Sections

	for _, section := range sections {
		if section.Name == ".text" {
			data, _ = section.Data()
		}
	}
	return data, nil
}
