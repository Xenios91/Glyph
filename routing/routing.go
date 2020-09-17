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
		Title: "Glyph",
	}
	template := template.Must(template.ParseFiles("../templates/template.html", "../templates/main.html"))
	template.Execute(w, data)
}

func GetSymbolsPage(w http.ResponseWriter, r *http.Request) {
	var data pageData = pageData{
		Title: "Symbols",
	}
	template := template.Must(template.ParseFiles("../templates/template.html", "../templates/get_symbols.html"))
	template.Execute(w, data)
}

func UploadBinaryPage(w http.ResponseWriter, r *http.Request) {
	var data pageData = pageData{
		Title: "Binary Upload",
	}
	template := template.Must(template.ParseFiles("../templates/template.html", "../templates/upload.html"))
	template.Execute(w, data)
}
