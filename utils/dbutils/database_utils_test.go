package glyph

import (
	"database/sql"
	"fmt"
	utils "glyph/glyph/utils"
	bin_utils "glyph/glyph/utils/binutils"
	"os"
	"strings"
	"testing"

	_ "github.com/mattn/go-sqlite3"
)

func TestDB(t *testing.T) {
	defer os.Remove("./testTable")
	tableName := MLTrainingSetTableName
	testTableLocation := "./testTable"
	function := new(bin_utils.FunctionDetails)
	function.FunctionName = "testFunction"
	function.LowAddress = "0x012345"
	function.HighAddress = "0x023456"
	function.Tokens = []string{"test", "test"}
	function.ReturnType = "void"
	binDetails := new(bin_utils.BinaryDetails)
	binDetails.BinaryName = "testBin"
	binDetails.FunctionsMap.FunctionDetails = make([]bin_utils.FunctionDetails, 1)
	binDetails.FunctionsMap.FunctionDetails[0] = *function
	values := make([]interface{}, 3)
	values[0] = testTableLocation
	values[1] = tableName
	values[2] = binDetails

	database, err := sql.Open("sqlite3", "./testTable")
	defer database.Close()
	utils.CheckError(err)
	preparedStatement := fmt.Sprintf("CREATE TABLE IF NOT EXISTS %s (id INTEGER PRIMARY KEY, %s TEXT, %s TEXT, %s TEXT, %s TEXT)", MLTrainingSetTableName, FunctionNameColumn, ReturnTypeColumn, TokensColumn, EntryPointColumn)
	statement, err := database.Prepare(preparedStatement)
	utils.CheckError(err)
	statement.Exec()

	type args struct {
		values []interface{}
	}
	tests := []struct {
		name string
		args args
	}{
		{name: "test1", args: args{values: values}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			InsertDB(tt.args.values...)
		})

		ps := fmt.Sprintf("SELECT * FROM %s WHERE %s=?", tableName, EntryPointColumn)
		param := "0x012345"
		results, _ := QueryDBWithParameter(testTableLocation, &ps, &param)
		var primKey int
		var functionName string
		var entryPoint string
		var tokens string
		var returnType string

		for results.Next() {
			results.Scan(&primKey, &functionName, &returnType, &tokens, &entryPoint)
		}
		if strings.Compare(entryPoint, "0x012345") != 0 {
			t.Errorf("QueryDBWithParameter returned the wrong function, got entrypoint %v want %v", entryPoint, "0x012345")
		}

		ps = fmt.Sprintf("DELETE FROM %s WHERE %s=?", tableName, EntryPointColumn)
		param = "0x012345"
		deleteFromDBWithParameter(testTableLocation, &ps, &param)
		ps = fmt.Sprintf("SELECT * FROM %s", tableName)
		results = QueryDB(testTableLocation, &ps)

		row := results.Next()
		if row {
			t.Errorf("QueryDB returned data, deleteFormDBWithParameter didnt work as intended. Returned %v want nil", row)
		}
	}
}
