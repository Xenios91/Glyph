package glyph

import (
	"fmt"
	"log"
	"os"
)

func createLogs() {
	file, err := os.OpenFile("./glyph.log", os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	defer file.Close()
	if err != nil {
		log.Fatal(err)
	}

	log.SetOutput(file)
	log.Print("Glyph Started")
}

func LoadLogging(enableLogging bool) {
	fmt.Print("Checking logging... ")
	if enableLogging {
		createLogs()
	}
	fmt.Printf("Logging enabled: %t\n", enableLogging)
}
