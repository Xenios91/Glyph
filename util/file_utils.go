package util

import "os"

func CheckIfFileExist(filename string) bool {
	fileInfo, err := os.Stat(filename)
	if os.IsNotExist(err) {
		return false
	}
	return !fileInfo.IsDir()
}
