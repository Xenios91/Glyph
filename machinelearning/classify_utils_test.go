package glyph

import (
	bin_utils "glyph/glyph/utils/binutils"
	"reflect"
	"strings"
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
		obtainedSlice := classes[class]
		expectedSlice := []string{"well hello", "hello there", "there there"}
		if !reflect.DeepEqual(obtainedSlice.Tokens, expectedSlice) {
			t.Errorf("populateNGrams create the wrong tokens list, got %v want %v", functionDetails.Tokens, expectedSlice)
		}
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
	for counter, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			setClassifierConfig(tt.args.nGrams)
		})
		got := classifierConfig.NGrams
		want := tests[counter].args.nGrams
		if got != want {
			t.Errorf("Classifier Config has incorrect N-Grams, got %v want %v", got, want)
		}
	}
}

func Test_populateReturnTypeMap(t *testing.T) {
	returnTypeMap = make(map[string][]bin_utils.FunctionDetails)
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
	for counter, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			populateReturnTypeMap(tt.args.classes)
		})
		returnTypeMapLength := len(returnTypeMap)
		if returnTypeMapLength != 1 {
			t.Errorf("ReturnTypeMap is unexpected size, got %v want %v", returnTypeMapLength, 1)
		}
		returnTypeVoidSlice := returnTypeMap["void"]
		obtainedFunction := returnTypeVoidSlice[counter]
		if !reflect.DeepEqual(obtainedFunction, *function) {
			t.Errorf("ReturnTypeMap stored incorrect function with return type %v got %v want %v", function.ReturnType, obtainedFunction, *function)
		}
	}

}

func Test_retrieveReturnTypeFromTokens(t *testing.T) {
	function := new(bin_utils.FunctionDetails)
	function.FunctionName = "testFunction"
	function.Tokens = []string{"undefined", "testFunction", "something", "something", "darkside"}
	want := "undefined"
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

func Test_populateReturnType(t *testing.T) {
	classifierConfig.NGrams = 2
	classes := make(map[bayesian.Class]bin_utils.FunctionDetails)
	function := new(bin_utils.FunctionDetails)
	function.FunctionName = "testFunction"
	function.Tokens = []string{"undefined", "testFunction", "something", "something", "darkside"}
	classes[bayesian.Class(function.FunctionName)] = *function
	classes2 := new(bin_utils.BinaryDetails)
	classes2.FunctionsMap.FunctionDetails = make([]bin_utils.FunctionDetails, 1)
	classes2.FunctionsMap.FunctionDetails[0] = *function

	type args struct {
		classes interface{}
	}
	tests := []struct {
		name string
		args args
	}{
		{name: "test1", args: args{classes: &classes}},
		{name: "test2", args: args{classes: classes2}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			populateReturnType(tt.args.classes)
			functionReturnType := classes[bayesian.Class(function.FunctionName)].ReturnType
			expectedType := "undefined"
			if strings.Compare(functionReturnType, expectedType) != 0 {
				t.Errorf("populateReturnType obtained the wrong return type, got %v want %v", functionReturnType, expectedType)
			}
		})

	}
}

func Test_createTrainingClassifiers(t *testing.T) {
	functionDetails := new(bin_utils.FunctionDetails)
	functionDetails.FunctionName = "testFunction"
	functionDetails.ReturnType = "void"
	returnTypeMap = make(map[string][]bin_utils.FunctionDetails)
	returnTypeMap[functionDetails.ReturnType] = append(make([]bin_utils.FunctionDetails, 0), *functionDetails)

	tests := []struct {
		name string
	}{
		{name: "test1"},
	}
	for counter, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			createTrainingClassifiers()
		})
		classifier := classifier[functionDetails.ReturnType]
		class := string(classifier.Classes[counter])
		if strings.Compare(class, functionDetails.FunctionName) != 0 {
			t.Errorf("Classifier[0] has %v but should have %v", class, functionDetails.FunctionName)
		}
	}

}

func Test_removeExtraData(t *testing.T) {
	functionDetails := new(bin_utils.FunctionDetails)
	functionName := "testFunction"
	functionTokens := []string{"void", "testFunction", "well", "hello", "there"}
	functionDetails.FunctionName = functionName
	functionDetails.Tokens = functionTokens
	data := make(map[bayesian.Class]bin_utils.FunctionDetails)
	data[bayesian.Class(functionDetails.FunctionName)] = *functionDetails
	data2 := new(bin_utils.FunctionDetails)
	data2.FunctionName = functionName
	data2.Tokens = functionTokens

	type args struct {
		data interface{}
	}
	tests := []struct {
		name string
		args args
	}{
		{name: "test1", args: args{data: &data}}, {name: "test2", args: args{data: data2}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			removeExtraData(tt.args.data)
		})
		expectedTokens := []string{"well", "hello", "there"}
		gotTokens := data[bayesian.Class(functionDetails.FunctionName)].Tokens
		if !reflect.DeepEqual(gotTokens, expectedTokens) {
			t.Errorf("removeExtraData didn't work as expected, got %v want %v ", functionDetails.Tokens, expectedTokens)
		}
	}

}
