package util

import (
	"io"
	"os"
	"path/filepath"
)

func CheckIfFileExist(filename string) bool {
	fileInfo, err := os.Stat(filename)
	if os.IsNotExist(err) {
		return false
	}
	return !fileInfo.IsDir()
}

func IOReader(file string) io.ReaderAt {
	reader, err := os.Open(file)
	CheckError(err)
	return reader
}

func CreateDirectory(directoryParent string, directoryName string) (string, error) {
	dirPath := filepath.Join(directoryParent, directoryName)
	err := os.MkdirAll(dirPath, os.ModePerm)
	return dirPath, err
}
