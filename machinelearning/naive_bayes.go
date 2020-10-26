package glyph

import (
	"fmt"
	bin_utils "glyph/glyph/utils/binutils"
	"math"
	"strings"

	"github.com/navossoc/bayesian"
)

var classifier map[string]*bayesian.Classifier = make(map[string]*bayesian.Classifier, 10)
var returnTypeMap map[string][]bin_utils.FunctionDetails = make(map[string][]bin_utils.FunctionDetails, 10)
var trainingDataCheck map[string]int = make(map[string]int, 3)

func CreateClassifier(classes *map[bayesian.Class]bin_utils.FunctionDetails) {
	fmt.Print("Beginning to classify training data...")
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
	fmt.Println("Training data classification complete!")
}

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
				symbolTable.PopulateMap(function.LowAddress, string(functionName), confidence)
			}

		}

	}
	symbolTable.BinaryName = binary.BinaryName
	printClassificationDetails(functions)
	return symbolTable
}

func getNGrams(function *bin_utils.FunctionDetails) []string {
	var gramArray []string
	var tokensLength int = len(function.Tokens)
	var tokens []string = function.Tokens
	for counter := 0; counter < tokensLength; counter++ {
		if (counter + 1) == tokensLength {
			gramArray = append(gramArray, fmt.Sprintf("%s", tokens[counter]))
		} else {
			gramArray = append(gramArray, fmt.Sprintf("%s %s", tokens[counter], tokens[counter+1]))
		}
	}
	return gramArray
}

func printClassificationDetails(functions []bin_utils.FunctionDetails) {
	fmt.Println("Functions Classified!")
	fmt.Printf("Total functions analyzed: %d Total correct: %d Total incorrect: %d Total Errored: %d\n", len(functions), int(trainingDataCheck["correct"]), int(trainingDataCheck["incorrect"]), int(trainingDataCheck["error"]))
	fmt.Printf("%s %.2f%%\n", "Training accuracy:", (float64(trainingDataCheck["correct"]))/((float64(trainingDataCheck["correct"]))+float64(trainingDataCheck["incorrect"]))*100)
}

func getFunctionRange(function *bin_utils.FunctionDetails) (int, int) {
	var functionLength int = len(function.Tokens)
	var functionRange int = int(float32(functionLength) * 0.25)
	var highEnd int = functionLength + functionRange
	var lowEnd int = functionLength - functionRange
	return lowEnd, highEnd
}

func classifyFunction(function *bin_utils.FunctionDetails) (string, float64) {
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

	addressMatch := false
	for counter := range returnTypeArray {
		nameToCheck := returnTypeArray[counter].FunctionName
		if strings.Contains(classDetermined, nameToCheck) {
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

	return classDetermined, scores[likely]
}
