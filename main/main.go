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
	http.HandleFunc("/postFunctionDetails", routing.PostFunctionDetails)
	http.HandleFunc("/StatusUpdate", routing.StatusUpdate)
}

func startServer() {
	loadRoutes()
	http.ListenAndServe(":8080", nil)
}

func main() {
	Setup()
	var config *Configuration = &configuration
	if config.enableLogging {
		logging.CreateLogs()
	}
	startServer()
}
