package glyph

const (
	//MLTrainingSetTableName The table name for ML training sets.
	MLTrainingSetTableName string = "ML_Training_Sets"
	//MLTrainingSetTableLocation This is the location of the sqlite table for this data.
	MLTrainingSetTableLocation = "./database/ml_training_set/glyph_ml_training_set.db"
	//MLTrainingSetTableName The table name for ML training sets.
	SymbolTablesTableName string = "Symbol_Tables"
	//MLTrainingSetTableLocation This is the location of the sqlite table for this data.
	SymbolTablesTableLocation = "./database/ml_training_set/glyph_symbol_tables.db"

	LowAddressColumn   string = "lowAddress"
	HighAddressColumn  string = "highAddress"
	TokensColumn       string = "tokens"
	FunctionNameColumn string = "functionName"
	EntryPointColumn   string = "entryPoint"
)
