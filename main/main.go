package main

import (
	"horus/horus/logging"
	"horus/horus/routing"
	"net/http"
)

func loadRoutes() {
	http.HandleFunc("/", routing.MainPage)
}

func startServer() {
	loadRoutes()
	http.ListenAndServe(":8080", nil)
}

func main() {
	logging.CreateLogs()
	startServer()
}
