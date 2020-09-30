package machinelearning

import (
	"glyph/glyph/dbutils"
	"glyph/glyph/elftools"
	"strings"
)

//TrainWithData Processes the binaryDetails supplied and trains the ml model with the set.
func TrainWithData(binaryDetails *elftools.BinaryDetails) {
	functions := binaryDetails.FunctionsMap.FunctionDetails
	for _, function := range functions {
		lowAddress := function.LowAddress
		highAddress := function.HighAddress
		tokens := strings.Join(function.Tokens, " ")
		dbutils.InsertDB(dbutils.MLTrainingSetTableName, lowAddress, highAddress, tokens)
	}
}
