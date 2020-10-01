package glyph

import (
	"encoding/json"
	"fmt"
	ml "glyph/glyph/machinelearning"
	db_utils "glyph/glyph/utils/dbutils"
	logging "glyph/glyph/utils/logging"
	"os"
)

var configuration Configuration

//Configuration a struct for server configuration settings to be stored.
type Configuration struct {
	enableLogging bool
}

func loadConfig() {
	fmt.Print("Loading server configurations... ")
	file, _ := os.Open("./config/config.json")
	defer file.Close()
	decoder := json.NewDecoder(file)
	configuration = Configuration{}
	err := decoder.Decode(&configuration)
	if err != nil {
		fmt.Println("error:", err)
	}
	fmt.Println("Configurations loaded!")
}

func loadLogging() {
	fmt.Print("Checking logging... ")
	if configuration.enableLogging {
		logging.CreateLogs()
	}
	fmt.Printf("Logging enabled: %t\n", configuration.enableLogging)
}

//Setup Sets up the server
func Setup() {
	fmt.Println("Server starting...")
	loadConfig()
	loadLogging()
	db_utils.SetupDB()
	ml.LoadMLTrainingData()
	fmt.Println("Server started!")
}
