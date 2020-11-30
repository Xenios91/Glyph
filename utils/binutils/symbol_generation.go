package glyph

import "sync"

var lock sync.Mutex

//BinarySymbolTable A struct to represent a symbol table for a binary
type BinarySymbolTable struct {
	BinaryName string
	SymbolsMap map[string]string
}

//PopulateMap Used to populate the BinarySymbolTable struct's map with entry points and function names.
func (binarySymbolTable BinarySymbolTable) PopulateMap(entryPoint *string, functionName *string) {
	lock.Lock()
	defer lock.Unlock()
	binarySymbolTable.SymbolsMap[*entryPoint] = *functionName
}
