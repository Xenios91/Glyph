package main

import (
	"fmt"
	"glyph/glyph/elf_tools"
	"glyph/glyph/gapstone_tools"
	"glyph/glyph/logging"
	"glyph/glyph/routing"
	"net/http"
)

func loadRoutes() {
	http.HandleFunc("/", routing.MainPage)
	http.HandleFunc("/uploadBinary", routing.UploadBinaryPage)
	http.HandleFunc("/getSymbols", routing.GetSymbolsPage)
}

func startServer() {
	loadRoutes()
	http.ListenAndServe(":8080", nil)
}

func main() {
	var config *Configuration = loadConfig()
	if config.enableLogging {
		logging.CreateLogs()
	}
	testSection, _ := elf_tools.GetTextSection("../testbin")
	instructions, _ := gapstone_tools.GetInstructions(*testSection)
	fmt.Println(*instructions)
	startServer()
}
