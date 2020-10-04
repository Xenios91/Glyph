package glyph

import (
	"encoding/json"
	"fmt"
	ml "glyph/glyph/machinelearning"
	db_utils "glyph/glyph/utils/dbutils"
	ghidra_utils "glyph/glyph/utils/ghidrautils"
	logging "glyph/glyph/utils/logging"
	"os"
)

var config *configuration

//Configuration a struct for server configuration settings to be stored.
type configuration struct {
	EnableLogging         bool
	GhidraHeadless        string
	GhidraProjectLocation string
	GhidraProject         string
	GhidraScript          string
}

func loadConfig() {
	fmt.Print("Loading server configurations... ")
	file, _ := os.Open("./config/config.json")
	defer file.Close()
	decoder := json.NewDecoder(file)
	config = new(configuration)
	err := decoder.Decode(&config)
	if err != nil {
		fmt.Println("error:", err)
	}
	fmt.Println("Configurations loaded!")
}

func loadLogging() {
	fmt.Print("Checking logging... ")
	if config.EnableLogging {
		logging.CreateLogs()
	}
	fmt.Printf("Logging enabled: %t\n", config.EnableLogging)
}

func loadGhidraAnalysis() {
	fmt.Print("Loading Ghidra analysis queue... ")
	ghidra_utils.LoadGhidraAnalysis(config.GhidraHeadless, config.GhidraProjectLocation, config.GhidraProject, config.GhidraScript)
	fmt.Println("Ghidra Analysis Queue loaded!")
}

//Setup Sets up the server
func Setup() {
	fmt.Println("Server starting...")
	loadConfig()
	loadLogging()
	db_utils.SetupDB()
	ml.LoadMLTrainingData()
	loadGhidraAnalysis()
	fmt.Println("Server started!")
}
