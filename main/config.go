package main

import (
	"encoding/json"
	"fmt"
	"os"
)

type Configuration struct {
	enableLogging bool
}

func loadConfig() *Configuration {
	file, _ := os.Open("config.json")
	defer file.Close()
	decoder := json.NewDecoder(file)
	configuration := Configuration{}
	err := decoder.Decode(&configuration)
	if err != nil {
		fmt.Println("error:", err)
	}
	fmt.Println(configuration.enableLogging)
	return &configuration
}
