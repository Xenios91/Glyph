package routing

import (
	"encoding/json"
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

	tempFile, err := ioutil.TempFile(*dirPath, handler.Filename)
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

	util.StartGhidraAnalysis(tempFile.Name())
	return true
}

func PostFunctionDetails(w http.ResponseWriter, r *http.Request) {
	method := r.Method
	switch method {
	case "POST":
		var functionDetailsArray elf_tools.FunctionDetailsArray
		err := json.NewDecoder(r.Body).Decode(&functionDetailsArray)
		if err != nil {
			fmt.Println(err)
		}

		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(http.StatusOK)

	default:
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		fmt.Println(w, "POST request required")
	}

}

func StatusUpdate(w http.ResponseWriter, r *http.Request) {
	//todo
}
