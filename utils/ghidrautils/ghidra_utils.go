package glyph

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"sync"
)

type ghidraAnalysisQueue map[string]*ghidraQueueValue

type ghidraQueueValue struct {
	isTrainingData bool
	status         *string
}

type ghidraAnalysisConfig struct {
	ghidraHeadless        *string
	ghidraProjectLocation *string
	ghidraProject         *string
	ghidraScript          *string
}

var (
	once         sync.Once
	ghidraQueue  ghidraAnalysisQueue
	ghidraConfig *ghidraAnalysisConfig
)

//StartGhidraAnalysis Starts analysis on a supplied binary and returns a boolean value indicating if the analysis was successfully started.
func StartGhidraAnalysis(fileName string, trainingData bool) bool {
	addToQueue(filepath.Base(fileName), trainingData)
	err := exec.Command(*ghidraConfig.ghidraHeadless, *ghidraConfig.ghidraProjectLocation, *ghidraConfig.ghidraProject, "-import", fileName, "-postScript", *ghidraConfig.ghidraScript, "-overwrite").Start()
	if err != nil {
		fmt.Println(err)
		return false
	}
	return true
}

//LoadGhidraAnalysis sets all configuration information for ghidra based on arguments supplied.
func LoadGhidraAnalysis(ghidraHeadless *string, ghidraProjectLocation *string, ghidraProject *string, ghidraScript *string) {
	fmt.Print("Loading Ghidra analysis queue... ")
	once.Do(func() {
		ghidraQueue = make(ghidraAnalysisQueue)
		ghidraConfig = new(ghidraAnalysisConfig)

		ghidraConfig.ghidraHeadless = ghidraHeadless
		ghidraConfig.ghidraProjectLocation = ghidraProjectLocation
		ghidraConfig.ghidraProject = ghidraProject
		ghidraConfig.ghidraScript = ghidraScript
	})
	fmt.Println("Ghidra Analysis Queue successfully loaded!")
}

func addToQueue(binaryName string, trainingData bool) {
	var queueValue *ghidraQueueValue = new(ghidraQueueValue)
	queueValue.isTrainingData = trainingData
	ghidraQueue[binaryName] = queueValue
}

//RemoveFromQueue removes a binary name from the queue of binaries being processed by ghidra.
func RemoveFromQueue(binaryName string) {
	delete(ghidraQueue, binaryName)
}

//CheckIfTraining returns true/false if a binary being processed by ghidra currently is training data.
func CheckIfTraining(binaryName string) bool {
	return ghidraQueue[binaryName].isTrainingData
}

//CheckIfTrainingAndRemove returns true/false if a binary being processed by ghidra currently is training data, and removes it from the queue.
func CheckIfTrainingAndRemove(binaryName string) bool {
	var isTraining bool = ghidraQueue[binaryName].isTrainingData
	RemoveFromQueue(binaryName)
	return isTraining
}

//UpdateQueue updates the status of a binary currently in the queue.
func UpdateQueue(binaryName *string, statusUpdate *string) {
	var queueValue *ghidraQueueValue = ghidraQueue[*binaryName]
	if queueValue != nil {
		ghidraQueue[*binaryName].status = statusUpdate
	}
}
