package gapstone_tools

import (
	"log"

	"github.com/knightsc/gapstone"
)

func GetInstructions(data []byte) ([]gapstone.Instruction, error) {

	engine, err := gapstone.New(
		gapstone.CS_ARCH_X86,
		gapstone.CS_MODE_64,
	)

	instructions, err := engine.Disasm(
		data,    // code buffer
		0x10000, // starting address
		0,       // instructions to disassemble, 0 for all
	)

	if err == nil {
		defer engine.Close()

		if err == nil {
			log.Printf("Disasm:\n")
			for _, instruction := range instructions {
				log.Printf("0x%x:\t%s\t\t%s\n", instruction.Address, instruction.Mnemonic, instruction.OpStr)
			}
			return instructions, nil
		}
		log.Fatalf("Disassembly error: %v", err)
		return nil, err
	}
	log.Fatalf("Failed to initialize engine: %v", err)
	return nil, err

}
