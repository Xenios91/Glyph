package glyph

import (
	"fmt"
	bin_utils "glyph/glyph/utils/binutils"
	"math"
	"strings"

	"github.com/navossoc/bayesian"
)

type classifierConfiguration struct {
	NGrams int
}

var classifier = make(map[string]*bayesian.Classifier, 10)
var returnTypeMap = make(map[string][]bin_utils.FunctionDetails, 10)
var trainingDataCheck = make(map[string]int, 3)
var classifierConfig = new(classifierConfiguration)

func setClassifierConfig(nGrams int) {
	classifierConfig.NGrams = nGrams
	fmt.Printf("N-Grams set: %d... ", nGrams)
}

func populateReturnTypeMap(classes *map[bayesian.Class]bin_utils.FunctionDetails) {
	for _, function := range *classes {
		returnType := function.ReturnType
		returnTypeMap[returnType] = append(returnTypeMap[returnType], function)
	}
}

func populateNGrams(classes *map[bayesian.Class]bin_utils.FunctionDetails) {
	for key, function := range *classes {
		function.Tokens = getNGrams(&function)
		(*classes)[key] = function
	}
}

func retrieveReturnTypeFromTokens(function *bin_utils.FunctionDetails) *string {
	tokens := function.Tokens
	var returnType string
	for splitAt, token := range tokens {
		if strings.EqualFold(function.FunctionName, token) {
			returnType = strings.Join(tokens[:splitAt], "")
			if strings.Contains(returnType, "undefined") {
				returnType = "undefined"
			}
			break
		}
	}
	return &returnType
}

func populateReturnType(classes interface{}) {
	switch data := classes.(type) {
	case *map[bayesian.Class]bin_utils.FunctionDetails:
		for key, function := range *data {
			returnType := retrieveReturnTypeFromTokens(&function)
			function.ReturnType = *returnType
			(*data)[key] = function
		}
	case *bin_utils.BinaryDetails:
		functions := data.FunctionsMap.FunctionDetails
		for _, function := range functions {
			retrieveReturnTypeFromTokens(&function)
		}
	}
}

func createTrainingClassifiers() {
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
}

func removeExtraData(data interface{}) {
	switch data := data.(type) {
	case *map[bayesian.Class]bin_utils.FunctionDetails:
		for key, value := range *data {
			for splitAt, token := range value.Tokens {
				if strings.EqualFold(token, string(key)) {
					newTokens := value.Tokens[splitAt+1:]
					value.Tokens = newTokens
					(*data)[key] = value
					break
				}
			}
		}
	case *bin_utils.FunctionDetails:
		for splitAt, token := range data.Tokens {
			if strings.EqualFold(token, data.FunctionName) {
				data.Tokens = data.Tokens[splitAt+1:]
				return
			}
		}
	}
}

func classifyTrainingData(classes *map[bayesian.Class]bin_utils.FunctionDetails) {
	fmt.Print("Beginning to classify training data... ")
	populateReturnType(classes)
	removeExtraData(classes)
	populateNGrams(classes)
	populateReturnTypeMap(classes)
	createTrainingClassifiers()

	for key := range classifier {
		functions := returnTypeMap[key]
		for _, function := range functions {
			if !strings.Contains(function.FunctionName, "FUN_") {
				if !strings.Contains(string(key), "FUN_") {
					function.Tokens = getNGrams(&function)
					classifier[key].Learn(function.Tokens, bayesian.Class(function.FunctionName))
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
	symbolTable.SymbolsMap = make(map[string]string)
	functions := binary.FunctionsMap.FunctionDetails
	for _, function := range functions {
		var gramArray []string
		returnType := retrieveReturnTypeFromTokens(&function)
		function.ReturnType = *returnType
		removeExtraData(&function)
		function.Tokens = append(gramArray, getNGrams(&function)...)

		if strings.Contains(function.FunctionName, "FUN_") {
			functionName, prob := classifyFunction(&function)

			if strings.Contains(*functionName, ",") || strings.Contains(*functionName, "FUN_") {
				functionName = filterUnknownFunctions(functionName)
			}

			if !math.IsNaN(prob) && len(*functionName) > 0 {
				symbolTable.PopulateMap(&function.LowAddress, functionName)
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
		for i := 0; i < classifierConfig.NGrams; i++ {
			if counter < (tokensLength - classifierConfig.NGrams) {
				grams.WriteString(tokens[counter+i])
				if i != (classifierConfig.NGrams - 1) {
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

func createCandidatesClassifier(function *bin_utils.FunctionDetails) ([]bayesian.Class, map[string]bin_utils.FunctionDetails) {
	var candidateMapKeys []bayesian.Class
	candidateMap := make(map[string]bin_utils.FunctionDetails)
	returnType := function.ReturnType
	returnTypeArray := returnTypeMap[returnType]

	for _, element := range returnTypeArray {
		functionName := element.FunctionName
		candidateMapKeys = append(candidateMapKeys, bayesian.Class(functionName))
		candidateMap[functionName] = element

	}

	if len(candidateMapKeys) < 2 {
		candidateMapKeys = append(candidateMapKeys, bayesian.Class("DUMMY_CLASS_01"), bayesian.Class("DUMMY_CLASS_02"))
	} else if candidateMapKeys == nil {
		candidateMapKeys = append(candidateMapKeys, bayesian.Class("DUMMY_CLASS_01"), bayesian.Class("DUMMY_CLASS_02"))
	}

	return candidateMapKeys, candidateMap
}

func classifyFunction(function *bin_utils.FunctionDetails) (*string, float64) {
	classifierMapKeys, classifierMap := createCandidatesClassifier(function)
	rangeClassifier := bayesian.NewClassifier(classifierMapKeys[:]...)

	for counter := range classifierMapKeys {
		rangeClassifier.Learn(classifierMap[string(classifierMapKeys[counter])].Tokens, classifierMapKeys[counter])
	}

	scores, likely, strict := rangeClassifier.LogScores(function.Tokens)

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
		returnTypeArray := returnTypeMap[function.ReturnType]
		checkAccuracy(returnTypeArray, &classDetermined, function)
	}
	return &classDetermined, scores[likely]
}
