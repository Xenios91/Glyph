package main

import (
	"fmt"
	config "glyph/glyph/config"
	ml "glyph/glyph/machinelearning"
	routing "glyph/glyph/routing"
	db_utils "glyph/glyph/utils/dbutils"
	ghidra_utils "glyph/glyph/utils/ghidrautils"
	logging "glyph/glyph/utils/logging"
	"net/http"
)

func loadRoutes() {
	http.HandleFunc("/", routing.MainPage)
	http.HandleFunc("/uploadBinary", routing.UploadBinaryPage)
	http.HandleFunc("/getSymbols", routing.GetSymbolsPage)
	http.HandleFunc("/postFunctionDetails", routing.PostFunctionDetails)
	http.HandleFunc("/statusUpdate", routing.StatusUpdate)
	http.HandleFunc("/error", routing.ErrorPage)
}

func startServer(portToBind *string) {
	loadRoutes()
	http.ListenAndServe(*portToBind, nil)
}

func setup() *string {
	glyphConfig := config.SetupConfiguration()
	db_utils.SetupDB()
	ml.SetupML(glyphConfig.CheckTrainingAccuracy, glyphConfig.ClassificationDetailsFile, glyphConfig.NGrams, glyphConfig.ProbabilityThreshHold)
	ghidra_utils.LoadGhidraAnalysis(glyphConfig.GhidraHeadless, glyphConfig.GhidraProjectLocation, glyphConfig.GhidraProject, glyphConfig.GhidraScript)
	logging.LoadLogging(glyphConfig.EnableLogging)
	var port int = glyphConfig.ServerPort
	fmt.Printf("Glyph started on port %d!\n", port)
	var portToBind string = fmt.Sprintf(":%d", port)
	return &portToBind
}

func main() {
	var portToBind = setup()
	startServer(portToBind)
}
