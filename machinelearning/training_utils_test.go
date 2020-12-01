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
	classifierConfig.NGrams = 2
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
	fileContent := strings.TrimSuffix(string(fileContentBytes), "\n")
	expectedContent := "Function name: testfunction EntryPoint: 0x012345"
	if !strings.Contains(fileContent, expectedContent) {
		t.Errorf("Contents written by printFailedClassificationDetails are incorrect, got %v want %v", fileContent, expectedContent)
	}
}

func Test_printClassificationDetails(t *testing.T) {
	fileName := "classification_details.txt"
	defer os.Remove(fileName)
	classifierConfig.NGrams = 2
	functionDetails := make([]bin_utils.FunctionDetails, 0)

	type args struct {
		functions []bin_utils.FunctionDetails
	}
	tests := []struct {
		name string
		args args
	}{
		{
			name: "test1",
			args: args{functions: functionDetails},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			printClassificationDetails(tt.args.functions)
		})
	}

	fileContentBytes, err := ioutil.ReadFile(fileName)

	if err != nil {
		log.Fatal(err)
	}

	fileContent := strings.TrimSuffix(string(fileContentBytes), "\n")
	expectedContent := "N-Grams: 2\nTotal functions analyzed: 0\nTotal correct: 0\nTotal incorrect: 0\nTotal Errored: 0\nNLP accuracy: NaN%\nTotal accuracy NaN%"
	if !strings.Contains(fileContent, expectedContent) {
		t.Errorf("Contents written by printFailedClassificationDetails are incorrect, got %v want %v", fileContent, expectedContent)
	}
}

func Test_setTrainingConfig(t *testing.T) {
	testFileName := "testFileName"

	type args struct {
		checkTrainingAccuracy     bool
		classificationDetailsFile *string
	}
	tests := []struct {
		name string
		args args
	}{
		{
			name: "test1",
			args: args{checkTrainingAccuracy: true, classificationDetailsFile: &testFileName},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			setTrainingConfig(tt.args.checkTrainingAccuracy, tt.args.classificationDetailsFile)
		})
	}
	checkAccuracy := trainingConfig.CheckTrainingAccuracy
	classDetailsFile := trainingConfig.classificationDetailsFile

	if !checkAccuracy {
		t.Errorf("setTrainingConfig didn't set checkTrainingAccuracy properly, got %v want %v", checkAccuracy, true)
	}
	if strings.Compare(classDetailsFile, testFileName) != 0 {
		t.Errorf("setTrainingConfig didn't set classificationDetailsFile properly, got %v want %v", classDetailsFile, testFileName)
	}
}

func Test_checkAccuracy(t *testing.T) {
	defer os.Remove("./failed_to_classify.txt")
	classDetermined := "testFunction"
	functionDetails := new(bin_utils.FunctionDetails)
	functionDetails2 := new(bin_utils.FunctionDetails)
	functionDetails3 := new(bin_utils.FunctionDetails)
	functionDetails.LowAddress = "0x012345"
	functionDetails2.LowAddress = "0x112345"
	functionDetails3.LowAddress = "0x212345"
	functionDetails.FunctionName = "testFunction"

	trainingData = make([]bin_utils.FunctionDetails, 3)
	trainingData[0] = *functionDetails
	trainingData[1] = *functionDetails2

	type args struct {
		classDetermined *string
		function        *bin_utils.FunctionDetails
	}
	tests := []struct {
		name string
		args args
	}{
		{name: "test1", args: args{classDetermined: &classDetermined, function: functionDetails}},
		{name: "test2", args: args{classDetermined: &classDetermined, function: functionDetails2}},
		{name: "test3", args: args{classDetermined: &classDetermined, function: functionDetails3}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			checkAccuracy(tt.args.classDetermined, tt.args.function)
		})
	}
	correct := trainingDataCheck["correct"]
	incorrect := trainingDataCheck["incorrect"]
	err := trainingDataCheck["error"]
	if correct != 1 {
		t.Errorf("checkAccuracy gave the wrong numbers, correct got %v want %v", correct, 1)
	}
	if incorrect != 1 {
		t.Errorf("checkAccuracy gave the wrong numbers, incorrect got %v want %v", incorrect, 1)
	}
	if err != 1 {
		t.Errorf("checkAccuracy gave the wrong numbers, error got %v want %v", err, 1)
	}
}
