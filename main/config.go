package main

import (
	"encoding/json"
	"fmt"
	"os"
)

var binPath string
var configuration Configuration

type Configuration struct {
	enableLogging bool
}

func loadConfig() {
	file, _ := os.Open("config.json")
	defer file.Close()
	decoder := json.NewDecoder(file)
	configuration = Configuration{}
	err := decoder.Decode(&configuration)
	if err != nil {
		fmt.Println("error:", err)
	}
	fmt.Printf("Logging enabled: %t", configuration.enableLogging)
}

func Setup() {
	loadConfig()
}
