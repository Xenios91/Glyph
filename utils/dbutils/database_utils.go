package glyph

import (
	"database/sql"
	"fmt"
	utils "glyph/glyph/utils"
	bin_utils "glyph/glyph/utils/binutils"
	"strings"

	_ "github.com/mattn/go-sqlite3"
	"github.com/navossoc/bayesian"
)

//InsertDB Insert a record into the supplied table.
func InsertDB(values ...interface{}) {
	var tableLocation = values[0].(string)
	var tableName string = values[1].(string)

	if tableName == MLTrainingSetTableName {
		var binaryDetails *bin_utils.BinaryDetails = values[2].(*bin_utils.BinaryDetails)
		for _, function := range binaryDetails.FunctionsMap.FunctionDetails {
			functionName := function.Tokens[1]
			lowAddress := function.LowAddress
			highAddress := function.HighAddress
			tokens := strings.Join(function.Tokens, " ")
			preparedStatement := fmt.Sprintf("INSERT INTO %s (%s, %s, %s, %s) VALUES (?, ?, ?, ?)", tableName, functionName, lowAddress, highAddress, tokens)
			database, err := sql.Open("sqlite3", tableLocation)
			defer database.Close()

			statement, err := database.Prepare(preparedStatement)
			utils.CheckError(err)
			_, err = statement.Exec(values[2], values[3], values[4], values[5])
			utils.CheckError(err)
		}

	} else if tableName == SymbolTablesTableName {
		var symbolTable *bin_utils.BinarySymbolTable = values[2].(*bin_utils.BinarySymbolTable)
		for entryPoint, functionName := range symbolTable.SymbolsMap {
			preparedStatement := fmt.Sprintf("INSERT INTO %s (%s, %s, %s) VALUES (?, ?, ?)", tableName, BinaryName, EntryPointColumn, FunctionNameColumn)
			database, err := sql.Open("sqlite3", tableLocation)
			defer database.Close()

			statement, err := database.Prepare(preparedStatement)
			utils.CheckError(err)
			_, err = statement.Exec(symbolTable.BinaryName, entryPoint, functionName)
			utils.CheckError(err)
		}

	}

}

func QueryDB(preparedStatement *string) *sql.Rows {
	database, err := sql.Open("sqlite3", MLTrainingSetTableLocation)
	defer database.Close()
	statement, err := database.Prepare(*preparedStatement)
	utils.CheckError(err)
	result, err := statement.Query()
	utils.CheckError(err)
	return result
}

func GetTrainingData() *map[bayesian.Class]bin_utils.FunctionDetails {
	preparedStatement := fmt.Sprintf("SELECT * FROM %s", MLTrainingSetTableName)
	result := QueryDB(&preparedStatement)

	var functionDetailsArray []bin_utils.FunctionDetails

	for result.Next() {
		functionDetails := new(bin_utils.FunctionDetails)
		var primKey int
		var tokens string

		result.Scan(&primKey, &functionDetails.FunctionName, &functionDetails.LowAddress, &functionDetails.HighAddress, &tokens)

		functionDetails.FunctionName = fmt.Sprintf("%s_VERSION_%d", functionDetails.FunctionName, primKey)
		functionDetails.Tokens = strings.Fields(tokens)
		functionDetailsArray = append(functionDetailsArray, *functionDetails)
	}

	var classes map[bayesian.Class]bin_utils.FunctionDetails = make(map[bayesian.Class]bin_utils.FunctionDetails)
	for _, function := range functionDetailsArray {
		classes[bayesian.Class(function.FunctionName)] = function
	}
	return &classes
}
