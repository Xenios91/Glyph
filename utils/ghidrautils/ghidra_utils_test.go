package glyph

import (
	"reflect"
	"testing"
)

func Test_addToQueue(t *testing.T) {
	ghidraQueue = make(ghidraAnalysisQueue)
	type args struct {
		binaryName   string
		trainingData bool
	}
	tests := []struct {
		name string
		args args
	}{
		{
			name: "test1",
			args: args{
				binaryName:   "testBin",
				trainingData: true,
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			addToQueue(tt.args.binaryName, tt.args.trainingData)
		})
	}
	queueValue := ghidraQueue["testBin"]
	status := *queueValue.status
	if !queueValue.isTrainingData {
		t.Error("Training data returned false, expected true")
	}
	if status != "Waiting on Ghidra" {
		t.Errorf("ghidraQueue[testbin] = got %v wanted %v", status, "Waiting on Ghidra")
	}
}

func TestRemoveFromQueue(t *testing.T) {
	type args struct {
		binaryName string
	}
	tests := []struct {
		name string
		args args
	}{
		{name: "test1",
			args: args{
				binaryName: "testBinName",
			}},
	}
	ghidraQueue = make(ghidraAnalysisQueue)
	addToQueue("testBinName", false)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			RemoveFromQueue(tt.args.binaryName)
		})
	}
	queueValue := ghidraQueue["testBinName"]
	if queueValue != nil {
		t.Errorf("ghidraQueue[testbinName] got %v wanted %v", queueValue, nil)
	}
}

func Test_checkIfTraining(t *testing.T) {
	ghidraQueue = make(ghidraAnalysisQueue)
	binName := "testBinName"
	type args struct {
		binaryName *string
	}
	tests := []struct {
		name string
		args args
		want bool
	}{
		{
			name: "test1",
			args: args{binaryName: &binName},
			want: true,
		},
	}
	addToQueue(binName, true)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := checkIfTraining(tt.args.binaryName); got != tt.want {
				t.Errorf("checkIfTraining() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestCheckIfTrainingAndRemove(t *testing.T) {
	ghidraQueue = make(ghidraAnalysisQueue)
	type args struct {
		binaryName string
	}
	tests := []struct {
		name string
		args args
		want bool
	}{
		{
			name: "test1",
			args: args{binaryName: "testBinName"},
			want: true,
		},
	}
	addToQueue("testBinName", true)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := CheckIfTrainingAndRemove(tt.args.binaryName); got != tt.want {
				t.Errorf("CheckIfTrainingAndRemove() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestUpdateQueue(t *testing.T) {
	ghidraQueue = make(ghidraAnalysisQueue)
	binName := "testBinName"
	statUpdate := "testStatusUpdate"
	type args struct {
		binaryName   *string
		statusUpdate *string
	}
	tests := []struct {
		name string
		args args
	}{
		{
			name: "test1",
			args: args{binaryName: &binName, statusUpdate: &statUpdate},
		},
	}
	addToQueue(binName, false)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			UpdateQueue(tt.args.binaryName, tt.args.statusUpdate)
		})
	}

	got := ghidraQueue[binName].status
	if *got != statUpdate {
		t.Errorf("ghidraQueue[binName] got %v want %v", *got, statUpdate)
	}
}

func TestGetStatus(t *testing.T) {
	ghidraQueue = make(ghidraAnalysisQueue)
	binName := "testBinName"
	want := "Waiting on Ghidra"
	addToQueue(binName, true)
	type args struct {
		binaryName *string
	}
	tests := []struct {
		name string
		args args
		want *string
	}{
		{
			name: "test1",
			args: args{binaryName: &binName},
			want: &want,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := GetStatus(tt.args.binaryName); *got != *tt.want {
				t.Errorf("GetStatus() = %v, want %v", *got, *tt.want)
			}
		})
	}
}

func TestGetAllStatus(t *testing.T) {
	ghidraQueue = make(ghidraAnalysisQueue)
	binName := "testBinName"
	addToQueue(binName, true)
	testMap := make(map[string]*string)
	status := "Waiting on Ghidra"
	testMap[binName] = &status

	tests := []struct {
		name string
		want map[string]*string
	}{
		{
			name: "test1",
			want: testMap,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := GetAllStatus(); !reflect.DeepEqual(got, tt.want) {
				t.Errorf("GetAllStatus() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestStartGhidraAnalysis(t *testing.T) {
	//junk value used to cause exec.command() to err when run so we can get false back as intended.
	junkValue := "-test"

	type args struct {
		fileName     string
		trainingData bool
	}
	tests := []struct {
		name string
		args args
		want bool
	}{
		{
			name: "test1",
			args: args{
				fileName:     "testFileName",
				trainingData: false,
			},
			want: false,
		},
	}
	LoadGhidraAnalysis(&junkValue, &junkValue, &junkValue, &junkValue)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := StartGhidraAnalysis(tt.args.fileName, tt.args.trainingData); got != tt.want {
				t.Errorf("StartGhidraAnalysis() = %v, want %v", got, tt.want)
			}
		})
	}
}
