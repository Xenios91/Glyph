package glyph

import (
	bin_utils "glyph/glyph/utils/binutils"
	db_utils "glyph/glyph/utils/dbutils"
	"strings"
)

func InsertTrainingData(binaryDetails *bin_utils.BinaryDetails) {
	functions := binaryDetails.FunctionsMap.FunctionDetails
	for _, function := range functions {
		functionName := function.Tokens[1]
		lowAddress := function.LowAddress
		highAddress := function.HighAddress
		tokens := strings.Join(function.Tokens, " ")
		db_utils.InsertDB(db_utils.MLTrainingSetTableName, functionName, lowAddress, highAddress, tokens)
	}
}
