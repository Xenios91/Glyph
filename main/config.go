package main

import (
	"encoding/json"
	"fmt"
	"glyph/glyph/dbutils"
	"os"
)

var configuration Configuration

//Configuration a struct for server configuration settings to be stored.
type Configuration struct {
	enableLogging bool
}

func loadConfig() {
	fmt.Println("Loading server configurations...")
	file, _ := os.Open("config.json")
	defer file.Close()
	decoder := json.NewDecoder(file)
	configuration = Configuration{}
	err := decoder.Decode(&configuration)
	if err != nil {
		fmt.Println("error:", err)
	}
	fmt.Println("Configurations loaded...")
}

func loadMLModel() {
	fmt.Println("Loading ML models...")

	fmt.Println("ML models loaded...")
}

//Setup Sets up the server
func Setup() {
	fmt.Println("Server starting...")
	loadConfig()
	fmt.Printf("Logging enabled: %t\n", configuration.enableLogging)
	dbutils.SetupDB()
	loadMLModel()
}
