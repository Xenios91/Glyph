package glyph

import (
	"fmt"
	"os/exec"
	"sync"
)

type ghidraAnalysisQueue map[string]bool

type ghidraAnalysisConfig struct {
	ghidraHeadless        string
	ghidraProjectLocation string
	ghidraProject         string
	ghidraScript          string
}

var (
	once         sync.Once
	ghidraQueue  ghidraAnalysisQueue
	ghidraConfig *ghidraAnalysisConfig
)

//StartGhidraAnalysis Starts analysis on a supplied binary
func StartGhidraAnalysis(fileName string, trainingData bool) bool {
	err := exec.Command(ghidraConfig.ghidraHeadless, ghidraConfig.ghidraProjectLocation, ghidraConfig.ghidraProject, "-import", fileName, "-postScript", ghidraConfig.ghidraScript, "-overwrite").Start()
	if err != nil {
		fmt.Println(err)
		return false
	}
	return true
}

func LoadGhidraAnalysis(ghidraHeadless string, ghidraProjectLocation string, ghidraProject string, ghidraScript string) {
	once.Do(func() {
		ghidraQueue = make(ghidraAnalysisQueue)
		ghidraConfig = new(ghidraAnalysisConfig)

		ghidraConfig.ghidraHeadless = ghidraHeadless
		ghidraConfig.ghidraProjectLocation = ghidraProjectLocation
		ghidraConfig.ghidraProject = ghidraProject
		ghidraConfig.ghidraScript = ghidraScript
	})
}

func AddToQueue(binaryName string, trainingData bool) {
	ghidraQueue[binaryName] = trainingData
}

func RemoveFromQueue(binaryName string) {
	delete(ghidraQueue, binaryName)
}

func CheckIfTraining(binaryName string) bool {
	return ghidraQueue[binaryName]
}

func CheckIfTrainingAndRemove(binaryName string) bool {
	var isTraining bool = ghidraQueue[binaryName]
	delete(ghidraQueue, binaryName)
	return isTraining
}
