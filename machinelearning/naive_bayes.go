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
