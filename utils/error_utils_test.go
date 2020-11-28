package glyph

import (
	"errors"
	"testing"
)

func TestCheckError(t *testing.T) {
	err := errors.New("test error")
	type args struct {
		err error
	}
	tests := []struct {
		name string
		args args
	}{
		{
			name: "test1",
			args: args{
				err: err,
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			defer func() {
				if r := recover(); r == nil {
					t.Errorf("The code did not panic as intended")
				}
			}()
			CheckError(tt.args.err)
		})
	}
}
