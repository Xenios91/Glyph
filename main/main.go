package main

import (
	"glyph/glyph/logging"
	"glyph/glyph/routing"
	"net/http"
)

func loadRoutes() {
	http.HandleFunc("/", routing.MainPage)
	http.HandleFunc("/uploadBinary", routing.UploadBinaryPage)
	http.HandleFunc("/getSymbols", routing.GetSymbolsPage)
	http.HandleFunc("/status", routing.StatusUpdate)
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
	startServer()
}
