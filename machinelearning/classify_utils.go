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

var classifier = make(map[string]*bayesian.Classifier, 10)
var returnTypeMap = make(map[string][]bin_utils.FunctionDetails, 10)
var trainingDataCheck = make(map[string]int, 3)
var naiveBayesConfig = new(naiveBayesConfiguration)

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
		if strings.Contains(returnType, "Undefined") {
			returnType = "Undefined"
		}
		function.Tokens = getNGrams(&function)
		returnTypeMap[returnType] = append(returnTypeMap[returnType], function)
	}

	for key, element := range returnTypeMap {
		var trainingClasses []bayesian.Class

		elementLength := len(element)

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

func filterUnknownFunctions(functions *string) *string {
	var functionSB strings.Builder
	var functionsCSV string

	functionsArray := strings.Split(*functions, ",")

	for _, functionName := range functionsArray {
		if !strings.Contains(functionName, "FUN_") {
			functionSB.WriteString(fmt.Sprintf("%s, ", functionName))
		}
	}
	functionsCSV = functionSB.String()
	if len(functionsCSV) > 0 {
		functionsCSV = functionsCSV[:len(functionsCSV)-1]
	}
	return &functionsCSV
}

//ClassifyFunctions used to classify one or more functions provided to it.
func ClassifyFunctions(binary *bin_utils.BinaryDetails) *bin_utils.BinarySymbolTable {
	symbolTable := new(bin_utils.BinarySymbolTable)
	symbolTable.SymbolsMap = make(map[string][]string)
	functions := binary.FunctionsMap.FunctionDetails

	for _, function := range functions {
		var gramArray []string
		gramArray = append(gramArray, fmt.Sprintf("%s", function.Tokens[0]))
		gramArray = append(gramArray, getNGrams(&function)...)
		function.Tokens = gramArray
		function.ReturnType = gramArray[0]

		if strings.Contains(function.FunctionName, "FUN_") {
			functionName, prob := classifyFunction(&function)

			if strings.Contains(*functionName, ",") {
				functionName = filterUnknownFunctions(functionName)
			}

			if !math.IsNaN(prob) && !strings.Contains(*functionName, "FUN_") && len(*functionName) > 0 {
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
	tokens := function.Tokens
	tokensLength := len(tokens)
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
	functionLength := len(function.Tokens)
	functionRange := int(float32(functionLength) * naiveBayesConfig.FunctionRange)
	highEnd := functionLength + functionRange
	lowEnd := functionLength - functionRange
	return lowEnd, highEnd
}

func classifyFunction(function *bin_utils.FunctionDetails) (*string, float64) {
	returnType := function.ReturnType
	lowEnd, highEnd := getFunctionRange(function)
	classifierMap := make(map[string]bin_utils.FunctionDetails)
	var classifierMapKeys []bayesian.Class

	returnTypeArray := returnTypeMap[returnType]

	for _, element := range returnTypeArray {
		tokensLength := len(element.Tokens)
		functionName := element.FunctionName
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

	if trainingConfig.CheckTrainingAccuracy {
		checkAccuracy(returnTypeArray, &classDetermined, function)
	}
	return &classDetermined, scores[likely]
}
