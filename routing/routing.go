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
	Title   string
	Message string
}

type symbolPageData struct {
	Title            string
	SelectionVisible bool
	Binaries         []string
	SymbolTable      bin_utils.BinarySymbolTable
	GhidraQueue      map[string]*string
}

type status struct {
	Name   *string `json:"name"`
	Status *string `json:"status"`
}

//MainPage loads the main page for Glyph.
func MainPage(w http.ResponseWriter, r *http.Request) {
	data := pageData{
		Title: "Glyph",
	}
	template := template.Must(template.ParseFiles("./templates/template.html", "./templates/main.html"))
	template.Execute(w, data)
}

//GetSymbolsPage loads the symbols page for Glyph.
func GetSymbolsPage(w http.ResponseWriter, r *http.Request) {
	symbolPageData := new(symbolPageData)

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
			symbolPageData.GhidraQueue = ghidra_utils.GetAllStatus()
			var complete string

			if symbolPageData.Binaries == nil && len(symbolPageData.GhidraQueue) == 0 {
				symbolPageData.Binaries = make([]string, 1)
				message := "No Binaries Available"
				symbolPageData.Binaries[0] = message
				complete = "N/A"
				symbolPageData.GhidraQueue[message] = &complete
			} else {
				complete = "complete"
				for _, binaryName := range symbolPageData.Binaries {
					symbolPageData.GhidraQueue[binaryName] = &complete
				}
			}

			statusMap := ghidra_utils.GetAllStatus()
			for key, element := range statusMap {
				symbolPageData.GhidraQueue[key] = element
			}

			template := template.Must(template.ParseFiles("./templates/template.html", "./templates/get_symbols.html"))
			template.Execute(w, symbolPageData)
		}
	}
}

//ErrorPage a generic template error page for when request errors occur.
func ErrorPage(w http.ResponseWriter, r *http.Request) {
	data := pageData{
		Title: "Glyph",
	}
	errorType, errorFound := r.URL.Query()["type"]
	if errorFound {
		if errorType[0] == "uploadError" {
			data.Message = "Looks like there was an error uploading your binary!"
		} else if errorType[0] == "unsupportedMethod" {
			data.Message = "Unsupported Method!"
		} else {
			data.Message = "Looks like an unknown error occured!"
		}
	} else {
		data.Message = "Looks like an unknown error occured!"
	}

	template := template.Must(template.ParseFiles("./templates/template.html", "./templates/error.html"))
	template.Execute(w, data)
}

//UploadBinaryPage loads the page to upload a binary for Glyph.
func UploadBinaryPage(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodPost {
		success := uploadFile(r)
		if !success {
			w.WriteHeader(http.StatusBadRequest)
		}
	} else if r.Method == http.MethodGet {
		data := pageData{
			Title: "Glyph",
		}
		template := template.Must(template.ParseFiles("./templates/template.html", "./templates/upload.html"))
		template.Execute(w, data)
	} else {
		w.WriteHeader(http.StatusMethodNotAllowed)
	}
}

func uploadFile(r *http.Request) bool {
	trainingData := false
	directoryParent := "./binaries_upload"
	directoryName := "elf"

	//500mb limit
	r.ParseMultipartForm(524288000)
	file, handler, err := r.FormFile("binaryFile")
	defer file.Close()

	if err != nil {
		fmt.Println(err)
		return false
	}

	trainingDataChecked := r.Form.Get("trainingData")

	if trainingDataChecked == "true" {
		trainingData = true
		directoryParent = "./binary_training_upload"
	}

	if handler.Header.Get("Content-Type") != "application/octet-stream" {
		return false
	}

	dirPath, err := utils.CreateDirectory(&directoryParent, &directoryName)
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
	case http.MethodPost:

		var binaryDetails bin_utils.BinaryDetails
		err := json.NewDecoder(r.Body).Decode(&binaryDetails)
		if err != nil {
			fmt.Println(err)
		}

		isTraining := ghidra_utils.CheckIfTrainingAndRemove(binaryDetails.BinaryName)

		if isTraining {
			go ml.InsertTrainingData(&binaryDetails)
			fileToDelete := fmt.Sprintf("./binary_training_upload/elf/%s", binaryDetails.BinaryName)
			utils.DeleteFile(&fileToDelete)
		} else {
			fmt.Print("Beginning to classify functions...")
			symbolTable := ml.ClassifyFunctions(&binaryDetails)
			fmt.Println("Function classification complete!")
			db_utils.InsertDB(db_utils.SymbolTablesTableLocation, db_utils.SymbolTablesTableName, symbolTable)
			fileToDelete := fmt.Sprintf("./binaries_upload/elf/%s", binaryDetails.BinaryName)
			utils.DeleteFile(&fileToDelete)
		}

		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(http.StatusOK)

	default:
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(http.StatusBadRequest)
		fmt.Println(w, "POST request required")
	}

}

//StatusUpdate Accepts status updtes from Ghidra on current analysis being performed.
func StatusUpdate(w http.ResponseWriter, r *http.Request) {
	method := r.Method
	if method == http.MethodPost {

		var statusUpdate status
		err := json.NewDecoder(r.Body).Decode(&statusUpdate)
		if err != nil {
			fmt.Println(err)
		} else {
			ghidra_utils.UpdateQueue(statusUpdate.Name, statusUpdate.Status)
		}

	} else {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		w.WriteHeader(http.StatusMethodNotAllowed)
	}
}
