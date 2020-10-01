package main

import (
	config "glyph/glyph/config"
	routing "glyph/glyph/routing"
	"net/http"
)

func loadRoutes() {
	http.HandleFunc("/", routing.MainPage)
	http.HandleFunc("/uploadBinary", routing.UploadBinaryPage)
	http.HandleFunc("/getSymbols", routing.GetSymbolsPage)
	http.HandleFunc("/postFunctionDetails", routing.PostFunctionDetails)
	http.HandleFunc("/statusUpdate", routing.StatusUpdate)
}

func startServer() {
	loadRoutes()
	http.ListenAndServe(":8080", nil)
}

func main() {
	config.Setup()
	startServer()
}
