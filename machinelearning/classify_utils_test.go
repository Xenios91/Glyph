package glyph

import (
	bin_utils "glyph/glyph/utils/binutils"
	"reflect"
	"strings"
	"testing"
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
	classes := make([]bin_utils.FunctionDetails, 1)
	classes[0] = *functionDetails
	classifierConfig.NGrams = 2

	type args struct {
		classes *[]bin_utils.FunctionDetails
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
		obtainedSlice := classes[0]
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

func Test_removeExtraData(t *testing.T) {
	functionDetails := new(bin_utils.FunctionDetails)
	functionName := "testFunction"
	functionTokens := []string{"void", "testFunction", "well", "hello", "there"}
	functionDetails.FunctionName = functionName
	functionDetails.Tokens = append(*new([]string), functionTokens[:]...)
	data := make([]bin_utils.FunctionDetails, 2)
	data[0] = *functionDetails
	functionDetails2 := new(bin_utils.FunctionDetails)
	functionDetails2.FunctionName = functionName
	functionDetails2.Tokens = append(*new([]string), functionTokens[:]...)

	type args struct {
		data interface{}
	}
	tests := []struct {
		name string
		args args
	}{
		{name: "test1", args: args{data: &data}}, {name: "test2", args: args{data: functionDetails2}},
	}
	for counter, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			removeExtraData(tt.args.data)
		})
		expectedTokens := []string{"void", "well", "hello", "there"}
		dataType := reflect.TypeOf(tt.args.data).String()

		var gotTokens []string
		if strings.Compare(dataType, "*glyph.FunctionDetails") == 0 {
			gotTokens = functionDetails2.Tokens
		} else {
			gotTokens = data[counter].Tokens
		}
		if !reflect.DeepEqual(gotTokens, expectedTokens) {
			t.Errorf("removeExtraData didn't work as expected, got %v want %v ", functionDetails.Tokens, expectedTokens)
		}
	}

}

func Test_classifyTrainingData(t *testing.T) {
	functionDetails := make([]bin_utils.FunctionDetails, 1)
	functionDetails[0] = *new(bin_utils.FunctionDetails)
	classifierConfig.NGrams = 2
	functionDetails[0].FunctionName = "testFunction"
	functionDetails[0].ReturnType = "void"
	functionDetails[0].Tokens = []string{"void", "testFunction", "well", "hello", "there"}

	type args struct {
		functionDetails *[]bin_utils.FunctionDetails
	}
	tests := []struct {
		name string
		args args
	}{
		{name: "test1", args: args{functionDetails: &functionDetails}},
	}
	for counter, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			classifyTrainingData(tt.args.functionDetails)
			found := false
			for _, class := range classifier.Classes {
				if strings.Compare(string(class), functionDetails[counter].FunctionName) != 0 {
					found = true
					break
				}
			}
			if !found {
				t.Errorf("Classifier doesn't contain correct class, should have %v", functionDetails[counter].FunctionName)
			}

		})

	}
}
