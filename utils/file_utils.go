package glyph

import (
	"os"
	"path/filepath"
)

//CheckIfFileExist returns /true/false if a file exist.
func CheckIfFileExist(filename string) bool {
	fileInfo, err := os.Stat(filename)
	if os.IsNotExist(err) {
		return false
	}
	return !fileInfo.IsDir()
}

//IOReader will open a file associated with the supplied name and return the files pointer.
func IOReader(file string) *os.File {
	reader, err := os.Open(file)
	CheckError(err)
	return reader
}

//CreateDirectory will create a directory using the supplied arguments.
func CreateDirectory(directoryParent *string, directoryName *string) (*string, error) {
	dirPath := filepath.Join(*directoryParent, *directoryName)
	err := os.MkdirAll(dirPath, os.ModePerm)
	return &dirPath, err
}

//DeleteFile deletes the file located at the path passed as an argument.
func DeleteFile(fileName *string) {
	if CheckIfFileExist(*fileName) {
		var err = os.Remove(*fileName)
		CheckError(err)
	}
}

//CreateAndWriteFile creates a file if it doesn't exist and writes fileContents to the file.
func CreateAndWriteFile(fileName *string, fileContents *string, append bool) {
	var file *os.File
	defer file.Close()
	var err error
	if !CheckIfFileExist(*fileName) {
		file, err = os.Create(*fileName)
		CheckError(err)
	} else if !append {
		DeleteFile(fileName)
		file, err = os.Create(*fileName)
		CheckError(err)
	} else {
		file, err = os.OpenFile(*fileName,
			os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		CheckError(err)
	}
	file.WriteString(*fileContents)
}
