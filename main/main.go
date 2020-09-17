package main

import (
	"glyph/glyph/logging"
	"glyph/glyph/routing"
	"net/http"
)

func loadRoutes() {
	http.HandleFunc("/", routing.MainPage)
	http.HandleFunc("/getSymbols", routing.GetSymbolsPage)
}

func startServer() {
	loadRoutes()
	http.ListenAndServe(":8080", nil)
}

func main() {
	logging.CreateLogs()
	startServer()
}
