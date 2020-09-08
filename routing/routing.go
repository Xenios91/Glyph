package routing

import (
	"html/template"
	"net/http"
)

type pageData struct {
	Title string
}

func MainPage(w http.ResponseWriter, r *http.Request) {
	var data pageData = pageData{
		Title: "Horus",
	}
	template := template.Must(template.ParseFiles("../templates/main.html"))
	template.Execute(w, data)
}
