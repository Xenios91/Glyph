package routing

import (
	"fmt"
	"glyph/glyph/elf_tools"
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
	template := template.Must(template.ParseFiles("../templates/main.html"))
	template.Execute(w, data)
}

func GetSymbolsPage(w http.ResponseWriter, r *http.Request) {
	var text_section, err = elf_tools.GetTextSection("../testbin")
	if err != nil {
		fmt.Println("an error has occured")
	}
	fmt.Println(text_section)
}
