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
	ServerPort            int
	CheckTrainingAccuracy bool
	NGrams                int
	FunctionRange         float32
	GhidraHeadless        string
	GhidraProjectLocation string
	GhidraProject         string
	GhidraScript          string
}

func loadConfig() {
	fmt.Print("Loading Glyph configurations... ")
	file, _ := os.Open("./config/config.json")
	defer file.Close()
	decoder := json.NewDecoder(file)
	config = new(configuration)
	err := decoder.Decode(&config)
	if err != nil {
		fmt.Println("Configurations failed to load!")
		fmt.Println("error:", err)
	}
	fmt.Println("Configurations successfully loaded!")
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
	fmt.Println("Ghidra Analysis Queue successfully loaded!")
}

func setupML() {
	fmt.Print("Setting up ML configurations... ")
	ml.SetTrainingConfig(config.CheckTrainingAccuracy)
	ml.SetNaiveBayesConfig(config.NGrams, config.FunctionRange)
	fmt.Println("ML configurations successfully loaded!")
	ml.LoadMLTrainingData()
}

func setupDB() {
	db_utils.SetupDB()
}

//Setup performs server setup and returns the port set in config.json for the server to bind to.
func Setup() int {
	fmt.Println("Glyph starting...")
	loadConfig()
	loadLogging()
	setupDB()
	setupML()
	loadGhidraAnalysis()
	fmt.Printf("Glyph started on port %d!\n", config.ServerPort)
	return config.ServerPort
}
