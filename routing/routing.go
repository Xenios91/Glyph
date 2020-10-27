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

//MainPage loads the main page for Glyph.
func MainPage(w http.ResponseWriter, r *http.Request) {
	var data pageData = pageData{
		Title: "Glyph",
	}
	template := template.Must(template.ParseFiles("./templates/template.html", "./templates/main.html"))
	template.Execute(w, data)
}

//GetSymbolsPage loads the symbols page for Glyph.
func GetSymbolsPage(w http.ResponseWriter, r *http.Request) {
	var symbolPageData *symbolPageData = new(symbolPageData)

	symbolPageData.Title = "Glyph Symbol Tables"

	if r.Method == "GET" {
		binValues, binFound := r.URL.Query()["binary"]
		delValues, delFound := r.URL.Query()["binaryDel"]
		if binFound && len(binValues[0]) > 0 {
			symbolPageData.SelectionVisible = false

			symbolPageData.SymbolTable = *db_utils.GetSymbolTable(&binValues[0])
			template := template.Must(template.ParseFiles("./templates/template.html", "./templates/get_symbols.html"))
			template.Execute(w, symbolPageData)
		} else if delFound && len(delValues[0]) > 0 {
			db_utils.DelSymbolTable(&delValues[0])
			http.Redirect(w, r, "/getSymbols", http.StatusSeeOther)
		} else {
			symbolPageData.SelectionVisible = true
			symbolPageData.Binaries = *db_utils.GetDistinctBinaries()
			template := template.Must(template.ParseFiles("./templates/template.html", "./templates/get_symbols.html"))
			template.Execute(w, symbolPageData)
		}
	}
}

//UploadBinaryPage loads the page to upload a binary for Glyph.
func UploadBinaryPage(w http.ResponseWriter, r *http.Request) {
	method := r.Method
	if method == "POST" {
		success := uploadFile(r)
		if !success {
			http.Redirect(w, r, "/uploadBinary", http.StatusSeeOther)
		} else {
			http.Redirect(w, r, "/uploadBinary", http.StatusSeeOther)
		}
	} else {
		var data pageData = pageData{
			Title: "Glyph",
		}
		template := template.Must(template.ParseFiles("./templates/template.html", "./templates/upload.html"))
		template.Execute(w, data)
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

	trainingDataChecked := r.Form.Get("trainingData")

	if trainingDataChecked == "true" {
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

		for counter, function := range binaryDetails.FunctionsMap.FunctionDetails {
			binaryDetails.FunctionsMap.FunctionDetails[counter].FunctionName = function.Tokens[1]
			function.Tokens = append(function.Tokens[:1], function.Tokens[2:]...)
		}

		isTraining := ghidra_utils.CheckIfTrainingAndRemove(binaryDetails.BinaryName)
		if isTraining {
			go ml.InsertTrainingData(&binaryDetails)
		} else {
			fmt.Print("Beginning to classify functions...")
			symbolTable := ml.ClassifyFunctions(&binaryDetails)
			fmt.Println("Function classification complete!")
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

//StatusUpdate todo, currently does nothing.
func StatusUpdate(w http.ResponseWriter, r *http.Request) {
	//todo
}
