package elftools

//BinarySymbolTable A struct to represent a symbol table for a binary
type BinarySymbolTable struct {
	SymbolsMap map[string]string
}

//PopulateMap Used to populate the BinarySymbolTable struct's map with entry points and function names.
func (binarySymbolTable BinarySymbolTable) PopulateMap(entryPoint string, functionName string) {
	binarySymbolTable.SymbolsMap[entryPoint] = functionName
}
