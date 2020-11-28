package glyph

import (
	"bufio"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"testing"
)

func TestCreateAndWriteFile(t *testing.T) {
	fileName := "testFile"
	fileText := "test contents"

	type args struct {
		fileName     *string
		fileContents *string
		append       bool
	}
	tests := []struct {
		name string
		args args
	}{
		{
			name: "test1",
			args: args{
				fileName:     &fileName,
				fileContents: &fileText,
				append:       false,
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			defer os.Remove(fileName)
			CreateAndWriteFile(tt.args.fileName, tt.args.fileContents, tt.args.append)
			fileInfo, err := os.Stat(fileName)
			if os.IsNotExist(err) {
				t.Errorf("The file was not created and written to")
			} else {
				isDirectory := fileInfo.IsDir()
				if isDirectory {
					t.Errorf("A directory was created instead")
				} else {
					file, err := os.Open(fileName)
					if err != nil {
						log.Fatal(err)
					}
					defer file.Close()
					scanner := bufio.NewScanner(file)
					scanner.Split(bufio.ScanLines)
					fileContents := *new([]string)
					for scanner.Scan() {
						fileContents = append(fileContents, scanner.Text())
					}
					if len(fileContents) > 1 && fileContents[0] != fileText {
						t.Errorf("The file contains unexpected data")
					}
				}
			}
		})
	}
}

func TestIOReader(t *testing.T) {
	file, err := ioutil.TempFile("./", "testFile")
	if err != nil {
		log.Fatal(err)
	}
	defer os.Remove(file.Name())
	reader, err := os.Open(file.Name())
	if err != nil {
		t.Error("[want] resulted in an error when being created")
	}

	type args struct {
		file string
	}
	tests := []struct {
		name string
		args args
		want *os.File
	}{
		{
			name: "test1",
			args: args{
				file: file.Name(),
			},
			want: reader,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := IOReader(tt.args.file).Name()
			if got != tt.want.Name() {
				t.Errorf("IOReader() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestCreateDirectory(t *testing.T) {
	directoryName := "testDirectory"
	directoryParent := "./"
	expectedPath := filepath.Join(directoryParent, directoryName)
	defer os.Remove(expectedPath)

	type args struct {
		directoryParent *string
		directoryName   *string
	}
	tests := []struct {
		name    string
		args    args
		want    *string
		wantErr bool
	}{
		{
			name: "test1",
			args: args{
				directoryName:   &directoryName,
				directoryParent: &directoryParent,
			},
			want:    &expectedPath,
			wantErr: false,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := CreateDirectory(tt.args.directoryParent, tt.args.directoryName)
			if (err != nil) != tt.wantErr {
				t.Errorf("CreateDirectory() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if *got != *tt.want {
				t.Errorf("CreateDirectory() = %v, want %v", got, tt.want)
			}
		})
	}
}
