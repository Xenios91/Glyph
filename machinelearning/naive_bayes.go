package glyph

import (
	bin_utils "glyph/glyph/utils/binutils"

	"github.com/navossoc/bayesian"
)

var classifier *bayesian.Classifier

func CreateClassifier(classes *map[bayesian.Class]bin_utils.FunctionDetails) {
	var arraySize = len(*classes)
	var trainingClasses []bayesian.Class = make([]bayesian.Class, arraySize)

	var counter int = 0
	for key := range *classes {
		trainingClasses[counter] = key
		counter++
	}

	classifier = bayesian.NewClassifier(trainingClasses[:]...)

	for key, element := range *classes {
		classifier.Learn(element.Tokens, key)
	}
}

func ClassifyFunctions(binary *bin_utils.BinaryDetails) {
	var symbolTable *bin_utils.BinarySymbolTable = new(bin_utils.BinarySymbolTable)
	symbolTable.SymbolsMap = make(map[string]string)
	var functions []bin_utils.FunctionDetails = binary.FunctionsMap.FunctionDetails

	for _, function := range functions {
		functionName := classifyFunction(&function)
		symbolTable.PopulateMap(function.LowAddress, string(functionName))
	}
}

func classifyFunction(function *bin_utils.FunctionDetails) bayesian.Class {
	scores, _, _ := classifier.LogScores(function.Tokens)

	var highest int = 0
	for counter, score := range scores {
		if score > scores[highest] {
			highest = counter
		}
	}
	return classifier.Classes[highest]
}
