package glyph

import (
	"fmt"
	bin_utils "glyph/glyph/utils/binutils"
	db_utils "glyph/glyph/utils/dbutils"
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
	db_utils.InsertDB(db_utils.MLTrainingSetTableLocation, db_utils.MLTrainingSetTableName, binaryDetails)
	fmt.Print("Reloading training data... ")
	LoadMLTrainingData()
	fmt.Println("Training data successfully reloaded!")
}
