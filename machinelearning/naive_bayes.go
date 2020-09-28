package machinelearning

import (
	"fmt"

	"github.com/navossoc/bayesian"
)

const (
	Good bayesian.Class = "Good"
	Bad  bayesian.Class = "Bad"
	Taco bayesian.Class = "Taco"
)

func main() {
	classifier := bayesian.NewClassifier(Good, Bad, Taco)
	goodStuff := []string{}
	classifier.Learn(goodStuff, Good)

	probs, _, _ := classifier.LogScores(
		[]string{"yummy", "mexico"},
	)

	var highest int = 0
	for count, _ := range probs {
		if probs[count] > probs[highest] {
			highest = count
		}
	}
	fmt.Printf("The most likely classifier is: %s", classifier.Classes[highest])

}
