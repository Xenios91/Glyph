package glyph

import (
	"fmt"
	bin_utils "glyph/glyph/utils/binutils"

	"github.com/navossoc/bayesian"
)

func CreateClassifier(classes *map[bayesian.Class]bin_utils.FunctionDetails) error {
	var trainingClasses []bayesian.Class
	for key := range *classes {
		trainingClasses = append(trainingClasses, key)
	}

	classifier := bayesian.NewClassifier(trainingClasses[:]...)

	for key, element := range *classes {
		classifier.Learn(element.Tokens, key)
	}

	probs, _, _ := classifier.LogScores(
		[]string{},
	)

	var highest int = 0
	for count := range probs {
		if probs[count] > probs[highest] {
			highest = count
		}
	}
	fmt.Printf("The most likely classifier is: %s", classifier.Classes[highest])
	return nil
}
