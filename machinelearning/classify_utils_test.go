package glyph

import (
	bin_utils "glyph/glyph/utils/binutils"
	"reflect"
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
