package glyph

const (
	//MLTrainingSetTableName The table name for ML training sets.
	MLTrainingSetTableName string = "ML_Training_Sets"
	//MLTrainingSetTableLocation This is the location of the sqlite table for this data.
	mlTrainingSetTableLocation = "./database/ml_training_set/glyph_ml_training_set.db"

	LowAddressColumn   string = "lowAddress"
	HighAddressColumn  string = "highAddress"
	TokensColumn       string = "tokens"
	FunctionNameColumn string = "functionName"
)
