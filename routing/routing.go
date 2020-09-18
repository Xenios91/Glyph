package routing

import (
	"fmt"
	"glyph/glyph/elf_tools"
	"glyph/glyph/util"
	"html/template"
	"io/ioutil"
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
	method := r.Method
	if method == "POST" {
		success := uploadFile(r)
		if !success {
			//error page
		} else {
			//notify success
		}
	}
	template := template.Must(template.ParseFiles("../templates/template.html", "../templates/upload.html"))
	template.Execute(w, data)
}

func uploadFile(r *http.Request) bool {
	//500mb limit
	r.ParseMultipartForm(524288000)
	file, handler, err := r.FormFile("binaryFile")
	defer file.Close()
	if err != nil {
		fmt.Println(err)
		return false
	}

	if handler.Header.Get("Content-Type") != "application/octet-stream" {
		return false
	}

	var directoryParent string = "../binaries_upload"
	var directoryName string = "elf"

	dirPath, err := util.CreateDirectory(directoryParent, directoryName)
	util.CheckError(err)

	tempFile, err := ioutil.TempFile(dirPath, handler.Filename)
	defer tempFile.Close()

	if err != nil {
		fmt.Println(err)
	}

	fileBytes, err := ioutil.ReadAll(file)
	if err != nil {
		fmt.Println(err)
	}

	tempFile.Write(fileBytes)
	isElf := elf_tools.CheckIfElf(tempFile)
	if !isElf {
		return false
	}

	return true
}
