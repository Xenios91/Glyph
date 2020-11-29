package glyph

import (
	bin_utils "glyph/glyph/utils/binutils"
	"io/ioutil"
	"log"
	"os"
	"strings"
	"testing"
)

func Test_printFailedClassificationDetails(t *testing.T) {
	fileName := "failed_to_classify.txt"
	defer os.Remove(fileName)
	functionDetails := new(bin_utils.FunctionDetails)
	functionDetails.FunctionName = "testfunction"
	functionDetails.LowAddress = "0x012345"
	type args struct {
		functionDetails *bin_utils.FunctionDetails
	}
	tests := []struct {
		name string
		args args
	}{
		{
			name: "test1",
			args: args{functionDetails: functionDetails},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			printFailedClassificationDetails(tt.args.functionDetails)
		})
	}
	fileContentBytes, err := ioutil.ReadFile(fileName)

	if err != nil {
		log.Fatal(err)
	}
	fileContent := string(fileContentBytes)
	expectedContent := "Function name: testfunction EntryPoint: 0x012345\n"
	if strings.Compare(fileContent, expectedContent) != 0 {
		t.Errorf("Contents written by printFailedClassificationDetails are incorrect, got %v want %v", fileContent, expectedContent)
	}
}
