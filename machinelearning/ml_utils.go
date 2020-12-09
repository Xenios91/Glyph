package glyph

import (
	"fmt"
	"sync"
)

var once sync.Once

//SetupML loads configuration data into the machine learning structs.
func SetupML(checkTrainingAccuracy bool, classificationDetailsFile *string, nGrams int, probabilityThreshHold float64) {
	once.Do(func() {
		fmt.Print("Setting up ML configurations... ")
		setTrainingConfig(checkTrainingAccuracy, classificationDetailsFile)
		setClassifierConfig(nGrams, probabilityThreshHold)
		fmt.Println("ML configurations successfully loaded!")
		loadMLTrainingData()
		trainingDataCheck["correct"] = 0
		trainingDataCheck["incorrect"] = 0
		trainingDataCheck["error"] = 0
	})

}
