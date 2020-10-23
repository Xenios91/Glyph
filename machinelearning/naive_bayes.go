package glyph

import (
	"fmt"
	bin_utils "glyph/glyph/utils/binutils"
	"math"
	"strings"

	"github.com/navossoc/bayesian"
)

var classifier map[string]*bayesian.Classifier = make(map[string]*bayesian.Classifier)

func CreateClassifier(classes *map[bayesian.Class]bin_utils.FunctionDetails) {
	var returnTypeMap map[string][]bin_utils.FunctionDetails = make(map[string][]bin_utils.FunctionDetails)
	for _, function := range *classes {
		returnType := function.Tokens[0]
		returnTypeMap[returnType] = append(returnTypeMap[returnType], function)
	}
	for key, element := range returnTypeMap {
		var trainingClasses []bayesian.Class
		var elementLength int = len(element)

		for counter := 0; counter < elementLength; counter++ {
			trainingClasses = append(trainingClasses, bayesian.Class(element[counter].FunctionName))
		}
		if len(trainingClasses) == 1 {
			trainingClasses = append(trainingClasses, bayesian.Class("Unknown"))
		}
		classifier[key] = bayesian.NewClassifier(trainingClasses[:]...)
	}

	for key, element := range *classes {
		var gramArray []string
		if !strings.Contains(string(key), "FUN_") {
			tokensLength := len(element.Tokens)
			for counter := 0; counter < tokensLength; counter++ {
				if (counter + 1) == tokensLength {
					gramArray = append(gramArray, fmt.Sprintf("%s", element.Tokens[counter]))
				} else {
					gramArray = append(gramArray, fmt.Sprintf("%s %s", element.Tokens[counter], element.Tokens[counter+1]))
				}
			}
			//classifier.Learn(gramArray, key)
		}
	}
}

func ClassifyFunctions(binary *bin_utils.BinaryDetails) *bin_utils.BinarySymbolTable {
	var symbolTable *bin_utils.BinarySymbolTable = new(bin_utils.BinarySymbolTable)
	symbolTable.SymbolsMap = make(map[string][]string)
	var functions []bin_utils.FunctionDetails = binary.FunctionsMap.FunctionDetails

	for _, function := range functions {
		var gramArray []string
		var tokensLength = len(function.Tokens)
		gramArray = append(gramArray, fmt.Sprintf("%s", function.Tokens[0]))
		for counter := 1; counter < tokensLength; counter++ {
			if counter+1 == tokensLength {
				gramArray = append(gramArray, fmt.Sprintf("%s", function.Tokens[counter]))
			} else {
				gramArray = append(gramArray, fmt.Sprintf("%s %s", function.Tokens[counter], function.Tokens[counter+1]))
			}
		}
		function.Tokens = gramArray
		function.ReturnType = gramArray[0]

		if strings.Contains(function.FunctionName, "FUN_") {
			functionName, prob := classifyFunction(&function)
			if !math.IsNaN(prob) {
				var confidence string
				switch {
				case prob >= 0.9:
					confidence = "Very High"
					break
				case prob >= 0.75:
					confidence = "High"
					break
				case prob >= 0.5:
					confidence = "Medium"
					break
				case prob >= 0.35:
					confidence = "Low"
					break
				default:
					confidence = "Very Low"
					break
				}
				symbolTable.PopulateMap(function.LowAddress, string(functionName), confidence)
			}

		}

	}
	symbolTable.BinaryName = binary.BinaryName
	fmt.Println("Functions Classified!")
	return symbolTable
}

func classifyFunction(function *bin_utils.FunctionDetails) (bayesian.Class, float64) {
	//scores, likely, _ := classifier.ProbScores(function.Tokens)

	//return classifier.Classes[likely], scores[likely]
	return "test", 0.0
}
