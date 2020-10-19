package glyph

import (
	"database/sql"
	"errors"
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
		for entryPoint, functionData := range symbolTable.SymbolsMap {
			preparedStatement := fmt.Sprintf("INSERT INTO %s (%s, %s, %s, %s) VALUES (?, ?, ?, ?)", tableName, BinaryNameColumn, EntryPointColumn, FunctionNameColumn, ProbabilityColumn)
			database, err := sql.Open("sqlite3", tableLocation)
			defer database.Close()

			statement, err := database.Prepare(preparedStatement)
			utils.CheckError(err)
			probability := functionData[0]
			functionName := functionData[1]
			_, err = statement.Exec(symbolTable.BinaryName, entryPoint, functionName, probability)
			utils.CheckError(err)
		}
	}
}

func QueryDBWithParameter(tableLocation string, preparedStatement *string, parameter *string) (*sql.Rows, error) {
	if utils.CheckIfFileExist(tableLocation) {
		database, err := sql.Open("sqlite3", tableLocation)
		defer database.Close()
		statement, err := database.Prepare(*preparedStatement)
		utils.CheckError(err)
		result, err := statement.Query(parameter)
		utils.CheckError(err)
		return result, nil
	}
	return nil, errors.New("Database not available")
}

func deleteFromDBWithParameter(tableLocation string, preparedStatement *string, parameter *string) error {
	if utils.CheckIfFileExist(tableLocation) {
		database, err := sql.Open("sqlite3", tableLocation)
		defer database.Close()
		statement, err := database.Prepare(*preparedStatement)
		utils.CheckError(err)
		_, err = statement.Exec(parameter)
		utils.CheckError(err)
		return nil
	}
	return errors.New("Database not available")
}

func QueryDB(tableLocation string, preparedStatement *string) *sql.Rows {
	database, err := sql.Open("sqlite3", tableLocation)
	defer database.Close()
	statement, err := database.Prepare(*preparedStatement)
	utils.CheckError(err)
	result, err := statement.Query()
	utils.CheckError(err)
	return result
}

func GetTrainingData() *map[bayesian.Class]bin_utils.FunctionDetails {
	preparedStatement := fmt.Sprintf("SELECT * FROM %s", MLTrainingSetTableName)
	result := QueryDB(MLTrainingSetTableLocation, &preparedStatement)

	var functionDetailsArray []bin_utils.FunctionDetails

	for result.Next() {
		functionDetails := new(bin_utils.FunctionDetails)
		var primKey int
		var tokens string

		result.Scan(&primKey, &functionDetails.FunctionName, &functionDetails.LowAddress, &functionDetails.HighAddress, &tokens)

		functionDetails.FunctionName = fmt.Sprintf("%s%s_VERSION_%d%s", functionDetails.FunctionName, "%", primKey, "%")
		functionDetails.Tokens = strings.Fields(tokens)
		functionDetailsArray = append(functionDetailsArray, *functionDetails)
	}

	var classes map[bayesian.Class]bin_utils.FunctionDetails = make(map[bayesian.Class]bin_utils.FunctionDetails)
	for _, function := range functionDetailsArray {
		classes[bayesian.Class(function.FunctionName)] = function
	}
	return &classes
}

func GetDistinctBinaries() *[]string {
	var preparedStatement string = fmt.Sprintf("SELECT DISTINCT %s FROM %s", BinaryNameColumn, SymbolTablesTableName)
	results := QueryDB(SymbolTablesTableLocation, &preparedStatement)

	var binaryName string
	var binaryNames []string = *new([]string)

	for results.Next() {
		results.Scan(&binaryName)
		binaryNames = append(binaryNames, binaryName)
	}
	return &binaryNames

}

func GetSymbolTable(binaryName *string) *bin_utils.BinarySymbolTable {
	var preparedStatement string = fmt.Sprintf("SELECT * FROM %s WHERE %s=?", SymbolTablesTableName, BinaryNameColumn)
	results, err := QueryDBWithParameter(SymbolTablesTableLocation, &preparedStatement, binaryName)
	utils.CheckError(err)
	var primKey int
	var entryPoint string
	var functionName string
	var probability string
	var symbolTable *bin_utils.BinarySymbolTable = new(bin_utils.BinarySymbolTable)
	symbolTable.SymbolsMap = make(map[string][]string)

	for results.Next() {
		results.Scan(&primKey, &symbolTable.BinaryName, &entryPoint, &functionName, &probability)
		functionName := strings.Split(functionName, "%_VERSION_")[0]
		symbolTable.PopulateMap(entryPoint, functionName, probability)
	}
	return symbolTable
}

func DelSymbolTable(binaryName *string) {
	var preparedStatement string = fmt.Sprintf("DELETE FROM %s WHERE %s=?", SymbolTablesTableName, BinaryNameColumn)
	err := deleteFromDBWithParameter(SymbolTablesTableLocation, &preparedStatement, binaryName)
	utils.CheckError(err)
}
