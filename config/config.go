package glyph

import (
	"encoding/json"
	"fmt"
	"os"
)

var config *Configuration

//Configuration a struct for server configuration settings to be stored.
type Configuration struct {
	EnableLogging             bool
	ServerPort                int
	CheckTrainingAccuracy     bool
	ClassificationDetailsFile *string
	NGrams                    int
	FunctionRange             float32
	GhidraHeadless            *string
	GhidraProjectLocation     *string
	GhidraProject             *string
	GhidraScript              *string
}

func loadConfig() {
	fmt.Print("Loading Glyph configurations... ")
	file, _ := os.Open("./config/config.json")
	defer file.Close()
	decoder := json.NewDecoder(file)
	config = new(Configuration)
	err := decoder.Decode(&config)
	if err != nil {
		fmt.Println("Configurations failed to load!")
		fmt.Println("error:", err)
	}
	fmt.Println("Configurations successfully loaded!")
}

//SetupConfiguration performs server setup and returns glyphs configuration.
func SetupConfiguration() *Configuration {
	fmt.Println("Glyph starting...")
	loadConfig()
	return config
}
