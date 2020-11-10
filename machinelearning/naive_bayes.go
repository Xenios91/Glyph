package glyph

import (
	"fmt"
	bin_utils "glyph/glyph/utils/binutils"
	"math"
	"strings"

	"github.com/navossoc/bayesian"
)

type naiveBayesConfiguration struct {
	NGrams        int
	FunctionRange float32
}

var classifier map[string]*bayesian.Classifier = make(map[string]*bayesian.Classifier, 10)
var returnTypeMap map[string][]bin_utils.FunctionDetails = make(map[string][]bin_utils.FunctionDetails, 10)
var trainingDataCheck map[string]int = make(map[string]int, 3)
var naiveBayesConfig *naiveBayesConfiguration = new(naiveBayesConfiguration)

func setNaiveBayesConfig(nGrams int, functionRange float32) {
	naiveBayesConfig.NGrams = nGrams
	naiveBayesConfig.FunctionRange = functionRange
	fmt.Printf("N-Grams set: %d... ", nGrams)
	fmt.Printf("Function Range set: %.2f... ", functionRange)
}

func createClassifier(classes *map[bayesian.Class]bin_utils.FunctionDetails) {
	fmt.Print("Beginning to classify training data... ")
	for _, function := range *classes {
		returnType := function.Tokens[0]
		function.Tokens = getNGrams(&function)
		returnTypeMap[returnType] = append(returnTypeMap[returnType], function)
	}
	for key, element := range returnTypeMap {
		var trainingClasses []bayesian.Class
		var elementLength int = len(element)

		for counter := 0; counter < elementLength; counter++ {
			functionName := element[counter].FunctionName
			if !strings.Contains(functionName, "FUN_") {
				trainingClasses = append(trainingClasses, bayesian.Class(element[counter].FunctionName))
			}
		}
		if len(trainingClasses) == 1 {
			trainingClasses = append(trainingClasses, bayesian.Class("DUMMY_CLASS"))
		}
		classifier[key] = bayesian.NewClassifier(trainingClasses[:]...)
	}

	for key := range classifier {
		functions := returnTypeMap[key]
		for _, function := range functions {
			if !strings.Contains(function.FunctionName, "FUN_") {
				if !strings.Contains(string(key), "FUN_") {
					gramArray := getNGrams(&function)
					classifier[key].Learn(gramArray, bayesian.Class(function.FunctionName))
				}
			}
		}
	}
	fmt.Print("Training data classification complete! ")
}

//ClassifyFunctions used to classify one or more functions provided to it.
func ClassifyFunctions(binary *bin_utils.BinaryDetails) *bin_utils.BinarySymbolTable {
	var symbolTable *bin_utils.BinarySymbolTable = new(bin_utils.BinarySymbolTable)
	symbolTable.SymbolsMap = make(map[string][]string)
	var functions []bin_utils.FunctionDetails = binary.FunctionsMap.FunctionDetails

	for _, function := range functions {
		var gramArray []string
		gramArray = append(gramArray, fmt.Sprintf("%s", function.Tokens[0]))
		gramArray = append(gramArray, getNGrams(&function)...)
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
				case prob > 0:
					confidence = "Very Low"
				default:
					confidence = "Unknown"
					break
				}
				symbolTable.PopulateMap(&function.LowAddress, functionName, &confidence)
			}

		}

	}
	symbolTable.BinaryName = binary.BinaryName
	fmt.Println("Functions Classified!")

	if trainingConfig.CheckTrainingAccuracy {
		printClassificationDetails(functions)
	}

	return symbolTable
}

func getNGrams(function *bin_utils.FunctionDetails) []string {
	var gramArray []string
	var tokens []string = function.Tokens
	var tokensLength int = len(tokens)
	for counter := 0; counter < tokensLength; counter++ {
		var grams strings.Builder
		for i := 0; i < naiveBayesConfig.NGrams; i++ {
			if counter < (tokensLength - naiveBayesConfig.NGrams) {
				grams.WriteString(tokens[counter+i])
				if i != (naiveBayesConfig.NGrams - 1) {
					grams.WriteString(" ")
				}
			} else {
				grams.WriteString(tokens[counter])
			}
		}
		gramArray = append(gramArray, grams.String())
	}
	return gramArray
}

func getFunctionRange(function *bin_utils.FunctionDetails) (int, int) {
	var functionLength int = len(function.Tokens)
	var functionRange int = int(float32(functionLength) * naiveBayesConfig.FunctionRange)
	var highEnd int = functionLength + functionRange
	var lowEnd int = functionLength - functionRange
	return lowEnd, highEnd
}

func classifyFunction(function *bin_utils.FunctionDetails) (*string, float64) {
	returnType := function.ReturnType
	lowEnd, highEnd := getFunctionRange(function)
	var classifierMap map[string]bin_utils.FunctionDetails = make(map[string]bin_utils.FunctionDetails)
	var classifierMapKeys []bayesian.Class

	returnTypeArray := returnTypeMap[returnType]

	for _, element := range returnTypeArray {
		var tokensLength int = len(element.Tokens)
		var functionName = element.FunctionName
		if tokensLength >= lowEnd && tokensLength <= highEnd {
			classifierMapKeys = append(classifierMapKeys, bayesian.Class(functionName))
			classifierMap[functionName] = element
		}
	}
	if len(classifierMapKeys) < 2 {
		classifierMapKeys = append(classifierMapKeys, bayesian.Class("DUMMY_CLASS_01"), bayesian.Class("DUMMY_CLASS_02"))
	} else if classifierMapKeys == nil {
		classifierMapKeys = append(classifierMapKeys, bayesian.Class("DUMMY_CLASS_01"), bayesian.Class("DUMMY_CLASS_02"))
	}
	rangeClassifier := bayesian.NewClassifier(classifierMapKeys[:]...)
	for counter := range classifierMapKeys {
		rangeClassifier.Learn(classifierMap[string(classifierMapKeys[counter])].Tokens, classifierMapKeys[counter])
	}

	scores, likely, strict, err := rangeClassifier.SafeProbScores(function.Tokens)
	if err != nil {
		scores, likely, strict = rangeClassifier.LogScores(function.Tokens)
		fmt.Println()
	}
	classDetermined := string(rangeClassifier.Classes[likely])

	if strict != true {
		for counter := range scores {
			value := scores[counter]
			if value == scores[likely] && counter != likely {
				likelyFunction := string(rangeClassifier.Classes[counter])
				if !strings.Contains(classDetermined, likelyFunction) {
					classDetermined = fmt.Sprintf("%s, %s", classDetermined, string(rangeClassifier.Classes[counter]))
				}

			}
		}
	}

	if trainingConfig.CheckTrainingAccuracy {
		checkAccuracy(returnTypeArray, &classDetermined, function)
	}
	return &classDetermined, scores[likely]
}
