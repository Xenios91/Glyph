package glyph

import (
	bin_utils "glyph/glyph/utils/binutils"
	"reflect"
	"testing"

	"github.com/navossoc/bayesian"
)

func Test_getNGrams(t *testing.T) {
	function := new(bin_utils.FunctionDetails)
	function.Tokens = []string{"well", "hello", "there"}
	classifierConfig.NGrams = 2
	type args struct {
		function *bin_utils.FunctionDetails
	}
	tests := []struct {
		name string
		args args
		want []string
	}{
		{
			name: "test1",
			args: args{function: function},
			want: []string{"well hello", "hello there", "there there"},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := getNGrams(tt.args.function); !reflect.DeepEqual(got, tt.want) {
				t.Errorf("getNGrams() = %v, want %v", got, tt.want)
			}
		})
	}
}

func Test_createCandidatesClassifier(t *testing.T) {
	function := new(bin_utils.FunctionDetails)
	function.ReturnType = "void"
	function.FunctionName = "testFunction"
	function.LowAddress = "0x012345"
	functions := make([]bin_utils.FunctionDetails, 1)
	functions[0] = *function
	returnTypeMap["void"] = functions
	expectedMap := make(map[string]bin_utils.FunctionDetails)
	expectedMap[function.FunctionName] = *function

	type args struct {
		function *bin_utils.FunctionDetails
	}
	tests := []struct {
		name  string
		args  args
		want  []bayesian.Class
		want1 map[string]bin_utils.FunctionDetails
	}{
		{
			name: "test1",
			args: args{
				function: function,
			},
			want:  []bayesian.Class{"testFunction", "DUMMY_CLASS_01", "DUMMY_CLASS_02"},
			want1: expectedMap,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, got1 := createCandidatesClassifier(tt.args.function)
			if !reflect.DeepEqual(got, tt.want) {
				t.Errorf("createCandidatesClassifier() got = %v, want %v", got, tt.want)
			}
			if !reflect.DeepEqual(got1, tt.want1) {
				t.Errorf("createCandidatesClassifier() got1 = %v, want %v", got1, tt.want1)
			}
		})
	}
}

func Test_filterUnknownFunctions(t *testing.T) {
	functions := "FUN_test, test1, test2"
	wantFunctions := "test1, test2"

	type args struct {
		functions *string
	}
	tests := []struct {
		name string
		args args
		want *string
	}{
		{
			name: "test1",
			args: args{functions: &functions},
			want: &wantFunctions,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := filterUnknownFunctions(tt.args.functions); *got != *tt.want {
				t.Errorf("filterUnknownFunctions() = %v, want %v", got, tt.want)
			}
		})
	}
}

func Test_populateNGrams(t *testing.T) {
	functionDetails := new(bin_utils.FunctionDetails)
	functionDetails.FunctionName = "testFunction"
	functionDetails.ReturnType = "void"
	functionDetails.Tokens = []string{"well", "hello", "there"}
	classes := make(map[bayesian.Class]bin_utils.FunctionDetails)
	class := bayesian.Class(functionDetails.FunctionName)
	classes[class] = *functionDetails
	classifierConfig.NGrams = 2

	type args struct {
		classes *map[bayesian.Class]bin_utils.FunctionDetails
	}
	tests := []struct {
		name string
		args args
	}{
		{
			name: "test1",
			args: args{classes: &classes},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			populateNGrams(tt.args.classes)
		})
	}
	obtainedSlice := classes[class]
	expectedSlice := []string{"well hello", "hello there", "there there"}
	if !reflect.DeepEqual(obtainedSlice.Tokens, expectedSlice) {
		t.Errorf("populateNGrams create the wrong tokens list, got %v want %v", functionDetails.Tokens, expectedSlice)
	}
}

func Test_setClassifierConfig(t *testing.T) {
	type args struct {
		nGrams int
	}
	tests := []struct {
		name string
		args args
	}{
		{name: "test1", args: args{nGrams: 2}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			setClassifierConfig(tt.args.nGrams)
		})
	}

	got := classifierConfig.NGrams
	want := 2
	if got != want {
		t.Errorf("Classifier Config has incorrect N-Grams, got %v want %v", got, want)
	}
}

func Test_populateReturnTypeMap(t *testing.T) {
	classes := make(map[bayesian.Class]bin_utils.FunctionDetails)
	function := new(bin_utils.FunctionDetails)
	function.FunctionName = "testfunction"
	function.ReturnType = "void"
	classes[bayesian.Class(function.FunctionName)] = *function
	type args struct {
		classes *map[bayesian.Class]bin_utils.FunctionDetails
	}
	tests := []struct {
		name string
		args args
	}{
		{name: "test1", args: args{classes: &classes}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			populateReturnTypeMap(tt.args.classes)
		})
	}
	returnTypeMapLength := len(returnTypeMap)
	if returnTypeMapLength != 1 {
		t.Errorf("ReturnTypeMap is unexpected size, got %v want %v", returnTypeMapLength, 1)
	}
	returnTypeVoidSlice := returnTypeMap["void"]
	obtainedFunction := returnTypeVoidSlice[0]
	if !reflect.DeepEqual(obtainedFunction, *function) {
		t.Errorf("ReturnTypeMap stored incorrect function with return type %v got %v want %v", function.ReturnType, obtainedFunction, function)
	}
}

func Test_retrieveReturnTypeFromTokens(t *testing.T) {
	function := new(bin_utils.FunctionDetails)
	function.FunctionName = "testFunction"
	function.Tokens = []string{"void", "testFunction", "something", "something", "darkside"}
	want := "void"
	type args struct {
		function *bin_utils.FunctionDetails
	}
	tests := []struct {
		name string
		args args
		want *string
	}{
		{name: "test1", args: args{function: function}, want: &want},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := retrieveReturnTypeFromTokens(tt.args.function); *got != *tt.want {
				t.Errorf("retrieveReturnTypeFromTokens() = %v, want %v", *got, *tt.want)
			}
		})
	}
}
