package gapstone

import (
	"debug/elf"
	"fmt"
	"io"
	"log"
	"os"

	"github.com/knightsc/gapstone"
)

func check(e error) {
	if e != nil {
		panic(e)
	}
}

func ioReader(file string) io.ReaderAt {
	r, err := os.Open(file)
	check(err)
	return r
}

func main() {

	f := ioReader("testbin")
	_elf, err := elf.NewFile(f)
	check(err)

	// Read and decode ELF identifier
	var ident [16]uint8
	f.ReadAt(ident[0:], 0)
	check(err)

	if ident[0] != '\x7f' || ident[1] != 'E' || ident[2] != 'L' || ident[3] != 'F' {
		fmt.Printf("Bad magic number at %d\n", ident[0:4])
		os.Exit(1)
	}

	engine, err := gapstone.New(
		gapstone.CS_ARCH_X86,
		gapstone.CS_MODE_64,
	)

	var sections = _elf.Sections
	for _, section := range sections {
		if section.Name == ".text" {
			data, _ := section.Data()

			insns, err := engine.Disasm(
				data,    // code buffer
				0x10000, // starting address
				0,       // insns to disassemble, 0 for all
			)

			if err == nil {

				defer engine.Close()

				maj, min := engine.Version()
				log.Printf("Hello Capstone! Version: %v.%v\n", maj, min)

				if err == nil {
					log.Printf("Disasm:\n")
					var counter uint8 = 0
					for _, insn := range insns {
						log.Printf("0x%x:\t%s\t\t%s\n", insn.Address, insn.Mnemonic, insn.OpStr)
						if insn.Mnemonic == "endbr64" {
							counter = counter + 1
						}
					}
					fmt.Println(counter)
					return
				}
				log.Fatalf("Disassembly error: %v", err)
			}
			log.Fatalf("Failed to initialize engine: %v", err)
		}
	}
}
