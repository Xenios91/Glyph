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
func CreateDirectory(directoryParent string, directoryName string) (*string, error) {
	dirPath := filepath.Join(directoryParent, directoryName)
	err := os.MkdirAll(dirPath, os.ModePerm)
	return &dirPath, err
}
