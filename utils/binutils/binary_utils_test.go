package glyph

import (
	"io/ioutil"
	"log"
	"os"
	"testing"
)

func TestCheckIfElf(t *testing.T) {
	file, err := ioutil.TempFile("./", "testFile")
	if err != nil {
		log.Fatal(err)
	}
	defer os.Remove(file.Name())
	file.WriteString("TEST")
	file.Close()

	type args struct {
		file *os.File
	}
	tests := []struct {
		name string
		args args
		want bool
	}{
		{
			name: "test1",
			args: args{
				file: file,
			},
			want: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := CheckIfElf(tt.args.file); got != tt.want {
				t.Errorf("CheckIfElf() = %v, want %v", got, tt.want)
			}
		})
	}
}
