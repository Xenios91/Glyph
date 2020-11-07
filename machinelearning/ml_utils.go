package glyph

import (
	"fmt"
	"sync"
)

var once sync.Once

//SetupML loads configuration data into the machine learning structs.
func SetupML(checkTrainingAccuracy bool, classificationDetailsFile *string, nGrams int, functionRange float32) {
	once.Do(func() {
		fmt.Print("Setting up ML configurations... ")
		setTrainingConfig(checkTrainingAccuracy, classificationDetailsFile)
		setNaiveBayesConfig(nGrams, functionRange)
		fmt.Println("ML configurations successfully loaded!")
		loadMLTrainingData()
	})

}
