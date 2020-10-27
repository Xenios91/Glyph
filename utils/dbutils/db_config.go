package glyph

const (
	//MLTrainingSetTableName The table name for ML training sets.
	MLTrainingSetTableName string = "ML_Training_Sets"
	//MLTrainingSetTableLocation This is the location of the sqlite table for this data.
	MLTrainingSetTableLocation = "./database/ml_training_set/glyph_ml_training_set.db"
	//SymbolTablesTableName The table name for where symbol tables will be stored.
	SymbolTablesTableName string = "Symbol_Tables"
	//SymbolTablesTableLocation This is the location of the sqlite table for this data.
	SymbolTablesTableLocation = "./database/symbol_tables/glyph_symbol_tables.db"
	//LowAddressColumn is the column name associated with the lowest address of a function.
	LowAddressColumn string = "lowAddress"
	//HighAddressColumn is the column name associated with the highest address of a function.
	HighAddressColumn string = "highAddress"
	//TokensColumn is the column name associated with all tokens for a specific function.
	TokensColumn string = "tokens"
	//FunctionNameColumn is the column name for the name of a function.
	FunctionNameColumn string = "functionName"
	//EntryPointColumn is the column name associated with the entry point (lowest address) of a function.
	EntryPointColumn string = "entryPoint"
	//BinaryNameColumn is the column name associated with the name of a binary a function belongs to.
	BinaryNameColumn string = "binaryName"
	//ProbabilityColumn is the column name associated with the confidence level of a functions fingerprinting.
	ProbabilityColumn string = "probability"
)
