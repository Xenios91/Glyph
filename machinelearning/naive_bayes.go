package glyph

import (
	"fmt"
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

func ClassifyFunctions(binary *bin_utils.BinaryDetails) *bin_utils.BinarySymbolTable {
	var symbolTable *bin_utils.BinarySymbolTable = new(bin_utils.BinarySymbolTable)
	symbolTable.SymbolsMap = make(map[string][]string)
	var functions []bin_utils.FunctionDetails = binary.FunctionsMap.FunctionDetails

	for _, function := range functions {
		functionName, prob := classifyFunction(&function)
		var probability string = fmt.Sprintf("%.2f%%", (prob * 100))
		symbolTable.PopulateMap(function.LowAddress, string(functionName), probability)
	}
	symbolTable.BinaryName = binary.BinaryName
	return symbolTable
}

func classifyFunction(function *bin_utils.FunctionDetails) (bayesian.Class, float64) {
	scores, _, _ := classifier.ProbScores(function.Tokens)

	var highestProb int = 0
	for counter, score := range scores {
		if score > scores[highestProb] {
			highestProb = counter
		}
	}
	return classifier.Classes[highestProb], scores[highestProb]
}
