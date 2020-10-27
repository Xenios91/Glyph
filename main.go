package main

import (
	"fmt"
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

func startServer(portToBind string) {
	loadRoutes()
	http.ListenAndServe(portToBind, nil)
}

func main() {
	var port int = config.Setup()
	var portToBind string = fmt.Sprintf(":%d", port)
	startServer(portToBind)
}
