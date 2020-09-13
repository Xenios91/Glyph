package logging

import (
	"log"
	"os"
)

func CreateLogs() {
	file, err := os.OpenFile("./glyph.log", os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	defer file.Close()
	if err != nil {
		log.Fatal(err)
	}

	log.SetOutput(file)
	log.Print("Glyph Started")
}
