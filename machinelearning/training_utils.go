package glyph

import (
	"fmt"
	file_utils "glyph/glyph/utils"
	bin_utils "glyph/glyph/utils/binutils"
	db_utils "glyph/glyph/utils/dbutils"
	"strings"
)

type trainingConfiguration struct {
	CheckTrainingAccuracy     bool
	classificationDetailsFile string
}

var trainingConfig *trainingConfiguration = new(trainingConfiguration)

//SetTrainingConfig used to set the configuration for ML training.
func SetTrainingConfig(checkTrainingAccuracy bool, classificationDetailsFile *string) {
	trainingConfig.CheckTrainingAccuracy = checkTrainingAccuracy
	trainingConfig.classificationDetailsFile = *classificationDetailsFile
	fmt.Printf("Check training accuracy: %t... ", checkTrainingAccuracy)
}

//LoadMLTrainingData loads all training data in the database and classifies it.
func LoadMLTrainingData() {
	fmt.Print("Loading ML models... ")
	mlData := db_utils.GetTrainingData()
	if len(*mlData) > 0 {
		CreateClassifier(mlData)
		fmt.Println("ML models successfully loaded!")

	} else {
		fmt.Println("No ML training data found... Starting fresh!")
	}

}

//InsertTrainingData inserts all provided training data to the database.
func InsertTrainingData(binaryDetails *bin_utils.BinaryDetails) {
	db_utils.InsertDB(db_utils.MLTrainingSetTableLocation, db_utils.MLTrainingSetTableName, binaryDetails)
	fmt.Print("Reloading training data... ")
	LoadMLTrainingData()
	fmt.Println("Training data successfully reloaded!")
}

func checkAccuracy(returnTypeArray []bin_utils.FunctionDetails, classDetermined *string, function *bin_utils.FunctionDetails) *map[string]int {
	addressMatch := false
	for counter := range returnTypeArray {
		nameToCheck := returnTypeArray[counter].FunctionName
		if strings.Contains(*classDetermined, nameToCheck) {
			addressToCheck := returnTypeArray[counter].LowAddress
			if function.LowAddress == addressToCheck {
				trainingDataCheck["correct"]++
				addressMatch = true
				break
			}
		}
	}

	if !addressMatch {
		inMap := false
		for _, element := range returnTypeMap {
			for _, fnc := range element {
				if fnc.LowAddress == function.LowAddress {
					trainingDataCheck["incorrect"]++
					inMap = true
					break
				}
				if inMap {
					break
				}
			}
		}
		if !inMap {
			trainingDataCheck["error"]++
		}
	}
	return &trainingDataCheck
}

func printClassificationDetails(functions []bin_utils.FunctionDetails) {
	var classificationDetailsFile string = "./classification_details.txt"
	var stringBuilder strings.Builder
	stringBuilder.WriteString(fmt.Sprintf("N-Grams: %d\n", naiveBayesConfig.NGrams))
	stringBuilder.WriteString(fmt.Sprintf("Function Range: %.2f\n", naiveBayesConfig.FunctionRange))
	stringBuilder.WriteString(fmt.Sprintf("Total functions analyzed: %d Total correct: %d Total incorrect: %d Total Errored: %d\n", len(functions), int(trainingDataCheck["correct"]), int(trainingDataCheck["incorrect"]), int(trainingDataCheck["error"])))
	stringBuilder.WriteString(fmt.Sprintf("%s %.2f%%\n", "Training accuracy:", (float64(trainingDataCheck["correct"]))/((float64(trainingDataCheck["correct"]))+float64(trainingDataCheck["incorrect"]))*100))
	var classificationDetails string = stringBuilder.String()
	file_utils.CreateAndWriteFile(&classificationDetailsFile, &classificationDetails, false)
}
