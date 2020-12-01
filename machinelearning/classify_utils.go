package glyph

import (
	"fmt"
	bin_utils "glyph/glyph/utils/binutils"
	"math"
	"strings"
	"sync"

	"github.com/navossoc/bayesian"
)

type classifierConfiguration struct {
	NGrams int
}

var classifier *bayesian.Classifier
var trainingDataCheck = make(map[string]int32, 3)
var classifierConfig = new(classifierConfiguration)
var trainingData []bin_utils.FunctionDetails

func setClassifierConfig(nGrams int) {
	classifierConfig.NGrams = nGrams
	fmt.Printf("N-Grams set: %d... ", nGrams)
}

func populateNGrams(functionDetails *[]bin_utils.FunctionDetails) {
	for counter, function := range *functionDetails {
		(*functionDetails)[counter].Tokens = getNGrams(&function)
	}
}

func removeExtraData(data interface{}) {
	switch functionDetails := data.(type) {
	case *[]bin_utils.FunctionDetails:
		for counter, function := range *functionDetails {
			for splitAt, token := range function.Tokens {
				if strings.EqualFold(token, function.FunctionName) {
					newTokens := append(function.Tokens[:splitAt])
					(*functionDetails)[counter].ReturnType = strings.Join(newTokens, "")
					newTokens = append(newTokens, function.Tokens[splitAt+1:]...)
					(*functionDetails)[counter].Tokens = newTokens
					break
				}
			}
		}
	case *bin_utils.FunctionDetails:
		for splitAt, token := range functionDetails.Tokens {
			if strings.EqualFold(token, functionDetails.FunctionName) {
				newTokens := append(functionDetails.Tokens[:splitAt])
				newTokens = append(newTokens, functionDetails.Tokens[splitAt+1:]...)
				functionDetails.Tokens = newTokens
				return
			}
		}
	}
}

func createClassifier(functions *[]bin_utils.FunctionDetails) {
	classes := make(map[bayesian.Class]bool)
	for _, function := range *functions {
		classifierName := bayesian.Class(function.FunctionName)
		classes[classifierName] = true
	}

	size := len(classes)
	classesSlice := make([]bayesian.Class, size)
	counter := 0
	for className := range classes {
		classesSlice[counter] = className
		counter++
	}
	if len(classesSlice) < 1 {
		classesSlice = append(classesSlice, "DUMMY_CLASS_01")
	}
	if len(classesSlice) < 2 {
		classesSlice = append(classesSlice, "DUMMY_CLASS_02")
	}
	classifier = bayesian.NewClassifier(classesSlice[:]...)
}

func classifyTrainingData(functions *[]bin_utils.FunctionDetails) {
	fmt.Print("Beginning to classify training data... ")
	removeExtraData(functions)
	populateNGrams(functions)
	createClassifier(functions)

	if trainingConfig.CheckTrainingAccuracy {
		trainingData = *functions
	}

	for _, function := range *functions {
		if !strings.Contains(function.FunctionName, "FUN_") {
			classifier.Learn(function.Tokens, bayesian.Class(function.FunctionName))
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
			functionSB.WriteString(fmt.Sprintf("%s,", functionName))
		}
	}
	functionsCSV = functionSB.String()
	if len(functionsCSV) > 0 {
		functionsCSV = functionsCSV[:len(functionsCSV)-1]
	}
	functionsCSV = strings.TrimPrefix(functionsCSV, " ")
	functionsCSV = strings.TrimSuffix(functionsCSV, ",")
	return &functionsCSV
}

//ClassifyFunctions used to classify one or more functions provided to it.
func ClassifyFunctions(binary *bin_utils.BinaryDetails) *bin_utils.BinarySymbolTable {
	var wg sync.WaitGroup
	symbolTable := new(bin_utils.BinarySymbolTable)
	symbolTable.SymbolsMap = make(map[string]string)
	functions := binary.FunctionsMap.FunctionDetails
	for _, function := range functions {
		wg.Add(1)
		go func(function bin_utils.FunctionDetails, wg *sync.WaitGroup) {
			defer wg.Done()
			var gramArray []string
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
		}(function, &wg)
	}
	wg.Wait()
	symbolTable.BinaryName = binary.BinaryName
	fmt.Println("Functions Classified!")

	if trainingConfig.CheckTrainingAccuracy {
		printClassificationDetails(functions)
	}

	return symbolTable
}

func getNGrams(function *bin_utils.FunctionDetails) []string {
	if classifierConfig.NGrams == 1 {
		return function.Tokens
	}

	var gramArray []string
	tokens := function.Tokens
	tokensLength := len(tokens)
	for counter := 0; counter < tokensLength; counter++ {
		var grams strings.Builder
		for i := 0; i < classifierConfig.NGrams; i++ {
			if counter <= (tokensLength - classifierConfig.NGrams) {
				grams.WriteString(tokens[counter+i])
				if i != (classifierConfig.NGrams - 1) {
					grams.WriteString(" ")
				}
			} else {
				if i == (classifierConfig.NGrams - 1) {
					grams.WriteString(" ")
				}
				grams.WriteString(tokens[counter])
			}
		}
		gramArray = append(gramArray, grams.String())
	}
	return gramArray
}

func classifyFunction(function *bin_utils.FunctionDetails) (*string, float64) {
	scores, likely, strict := classifier.LogScores(function.Tokens)

	classDetermined := string(classifier.Classes[likely])

	if strict != true {
		for counter := range scores {
			value := scores[counter]
			if value == scores[likely] && counter != likely {
				likelyFunction := string(classifier.Classes[counter])
				if !strings.Contains(classDetermined, likelyFunction) {
					classDetermined = fmt.Sprintf("%s, %s", classDetermined, string(classifier.Classes[counter]))
				}
			}
		}
	}

	if trainingConfig.CheckTrainingAccuracy {
		checkAccuracy(&classDetermined, function)
	}
	return &classDetermined, scores[likely]
}
