package glyph

import (
	"encoding/json"
	"fmt"
	ml "glyph/glyph/machinelearning"
	utils "glyph/glyph/utils"
	bin_utils "glyph/glyph/utils/binutils"
	db_utils "glyph/glyph/utils/dbutils"
	ghidra_utils "glyph/glyph/utils/ghidrautils"
	"html/template"
	"io/ioutil"
	"net/http"
)

type pageData struct {
	Title string
}

type symbolPageData struct {
	Title            string
	SelectionVisible bool
	Binaries         []string
	SymbolTable      bin_utils.BinarySymbolTable
}

func MainPage(w http.ResponseWriter, r *http.Request) {
	var data pageData = pageData{
		Title: "Glyph",
	}
	template := template.Must(template.ParseFiles("./templates/template.html", "./templates/main.html"))
	template.Execute(w, data)
}

func GetSymbolsPage(w http.ResponseWriter, r *http.Request) {
	var symbolPageData *symbolPageData = new(symbolPageData)

	symbolPageData.Title = "Glyph Symbol Tables"

	if r.Method == "GET" {
		keyValues, found := r.URL.Query()["binary"]
		if !found || len(keyValues[0]) < 1 {
			symbolPageData.SelectionVisible = true
			symbolPageData.Binaries = *db_utils.GetDistinctBinaries()
			template := template.Must(template.ParseFiles("./templates/template.html", "./templates/get_symbols.html"))
			template.Execute(w, symbolPageData)
		} else {
			symbolPageData.SelectionVisible = false
			symbolPageData.SymbolTable = *db_utils.GetSymbolTable(&keyValues[0])
			template := template.Must(template.ParseFiles("./templates/template.html", "./templates/get_symbols.html"))
			template.Execute(w, symbolPageData)
		}

	} else {

	}
}

func UploadBinaryPage(w http.ResponseWriter, r *http.Request) {
	method := r.Method
	if method == "POST" {
		success := uploadFile(r)
		if !success {
			http.Redirect(w, r, "/", http.StatusSeeOther)
		} else {
			http.Redirect(w, r, "/", http.StatusSeeOther)
		}
	}
}

func uploadFile(r *http.Request) bool {
	var trainingData bool = false
	var directoryParent string = "./binaries_upload"
	var directoryName string = "elf"

	//500mb limit
	r.ParseMultipartForm(524288000)
	file, handler, err := r.FormFile("binaryFile")

	if err != nil {
		fmt.Println(err)
		return false
	}

	defer file.Close()

	trainingDataChecked := r.Form.Get("training-data")

	if trainingDataChecked == "on" {
		trainingData = true
		directoryParent = "./binary_training_upload"
	}

	if handler.Header.Get("Content-Type") != "application/octet-stream" {
		return false
	}

	dirPath, err := utils.CreateDirectory(directoryParent, directoryName)
	utils.CheckError(err)

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
	isElf := bin_utils.CheckIfElf(tempFile)
	if !isElf {
		return false
	}

	analysisStarted := ghidra_utils.StartGhidraAnalysis(tempFile.Name(), trainingData)
	if analysisStarted {
		return true
	}
	return false
}

//PostFunctionDetails The function that handles the /postFunctionDetails endpoint, it processes a JSON consisting of function details.
func PostFunctionDetails(w http.ResponseWriter, r *http.Request) {
	method := r.Method
	switch method {
	case "POST":

		var binaryDetails bin_utils.BinaryDetails
		err := json.NewDecoder(r.Body).Decode(&binaryDetails)
		if err != nil {
			fmt.Println(err)
		}

		for _, function := range binaryDetails.FunctionsMap.FunctionDetails {
			function.Tokens[1] = "UNKNOWN"
		}

		isTraining := ghidra_utils.CheckIfTrainingAndRemove(binaryDetails.BinaryName)
		if isTraining {
			go ml.InsertTrainingData(&binaryDetails)
		} else {
			symbolTable := ml.ClassifyFunctions(&binaryDetails)
			db_utils.InsertDB(db_utils.SymbolTablesTableLocation, db_utils.SymbolTablesTableName, symbolTable)
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
