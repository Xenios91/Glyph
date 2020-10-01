package glyph

var ghidraAnalysisQueue = make(map[string]bool)

func AddToQueue(binaryName string, trainingData bool) {
	ghidraAnalysisQueue[binaryName] = trainingData
}

func RemoveFromQueue(binaryName string) {
	delete(ghidraAnalysisQueue, binaryName)
}

func CheckIfTraining(binaryName string) bool {
	return ghidraAnalysisQueue[binaryName]
}

func CheckIfTrainingAndRemove(binaryName string) bool {
	var isTraining bool = ghidraAnalysisQueue[binaryName]
	delete(ghidraAnalysisQueue, binaryName)
	return isTraining
}
