package glyph

//BinarySymbolTable A struct to represent a symbol table for a binary
type BinarySymbolTable struct {
	BinaryName string
	SymbolsMap map[string][]string
}

//PopulateMap Used to populate the BinarySymbolTable struct's map with entry points and function names.
func (binarySymbolTable BinarySymbolTable) PopulateMap(entryPoint string, functionName string, prob string) {
	if len(binarySymbolTable.SymbolsMap[entryPoint]) < 3 {
		binarySymbolTable.SymbolsMap[entryPoint] = append(binarySymbolTable.SymbolsMap[entryPoint], prob)
		binarySymbolTable.SymbolsMap[entryPoint] = append(binarySymbolTable.SymbolsMap[entryPoint], functionName)
	}

}
