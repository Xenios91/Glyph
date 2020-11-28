package glyph

import "testing"

func TestBinarySymbolTable_PopulateMap(t *testing.T) {
	testSymbolsMap := make(map[string]string)
	entryPoint := "0x012345"
	functionName := "testFunction"

	type fields struct {
		BinaryName string
		SymbolsMap map[string]string
	}
	type args struct {
		entryPoint   *string
		functionName *string
	}
	tests := []struct {
		name   string
		fields fields
		args   args
	}{
		{
			name: "test1",
			fields: fields{
				BinaryName: "testBin",
				SymbolsMap: testSymbolsMap,
			},
			args: args{
				entryPoint:   &entryPoint,
				functionName: &functionName,
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			binarySymbolTable := BinarySymbolTable{
				BinaryName: tt.fields.BinaryName,
				SymbolsMap: tt.fields.SymbolsMap,
			}
			binarySymbolTable.PopulateMap(tt.args.entryPoint, tt.args.functionName)
			got := binarySymbolTable.SymbolsMap[entryPoint]
			if got != functionName {
				t.Errorf("binarySymbolTable[\"testfunction\"] = %v, want %v", got, functionName)
			}
		})

	}
}
