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

func loadMLData() {
	fmt.Print("Loading ML models... ")
	mlData := db_utils.GetTrainingData()
	if len(*mlData) > 0 {
		err := ml.CreateClassifier(mlData)
		if err != nil {
			panic("ML DATA FAILED TO LOAD!")
		}
		fmt.Print("ML models loaded!")

	} else {
		fmt.Println("No ML training data found... Starting fresh!")
	}

}

//Setup Sets up the server
func Setup() {
	fmt.Println("Server starting...")
	loadConfig()
	loadLogging()
	db_utils.SetupDB()
	loadMLData()
	fmt.Println("Server started!")
}
