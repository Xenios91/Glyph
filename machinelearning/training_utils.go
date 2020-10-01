package glyph

import (
	"fmt"
	bin_utils "glyph/glyph/utils/binutils"
	db_utils "glyph/glyph/utils/dbutils"
	"strings"
)

func LoadMLTrainingData() {
	fmt.Print("Loading ML models... ")
	mlData := db_utils.GetTrainingData()
	if len(*mlData) > 0 {
		CreateClassifier(mlData)
		fmt.Println("ML models loaded!")

	} else {
		fmt.Println("No ML training data found... Starting fresh!")
	}

}

func InsertTrainingData(binaryDetails *bin_utils.BinaryDetails) {
	functions := binaryDetails.FunctionsMap.FunctionDetails
	for _, function := range functions {
		functionName := function.Tokens[1]
		lowAddress := function.LowAddress
		highAddress := function.HighAddress
		tokens := strings.Join(function.Tokens, " ")
		db_utils.InsertDB(db_utils.MLTrainingSetTableName, functionName, lowAddress, highAddress, tokens)
	}
	fmt.Print("Reloading training data... ")
	LoadMLTrainingData()
	fmt.Println("Training data successfully reloaded!")
}
