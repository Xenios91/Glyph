package machinelearning

import (
	"fmt"

	"github.com/navossoc/bayesian"
)

var classMap map[bayesian.Class][]string

func CreateClassifier(classes []bayesian.Class) {
	classifier := bayesian.NewClassifier(classes[:]...)

	for key, element := range classMap {
		classifier.Learn(element, key)
	}

	probs, _, _ := classifier.LogScores(
		[]string{"yummy", "mexico"},
	)

	var highest int = 0
	for count := range probs {
		if probs[count] > probs[highest] {
			highest = count
		}
	}
	fmt.Printf("The most likely classifier is: %s", classifier.Classes[highest])

}
