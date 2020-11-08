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
			tokens := strings.Join(function.Tokens, " ")
			preparedStatement := fmt.Sprintf("INSERT INTO %s (%s, %s, %s) VALUES (?, ?, ?)", tableName, FunctionNameColumn, TokensColumn, EntryPointColumn)
			database, err := sql.Open("sqlite3", tableLocation)
			defer database.Close()

			statement, err := database.Prepare(preparedStatement)
			utils.CheckError(err)
			_, err = statement.Exec(function.FunctionName, tokens, function.LowAddress)
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

//QueryDBWithParameter queries the table supplies with the statement provided and returns the results.
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

//QueryDB queries the database with at the table location provided with the statement and returns the result rows.
func QueryDB(tableLocation string, preparedStatement *string) *sql.Rows {
	database, err := sql.Open("sqlite3", tableLocation)
	defer database.Close()
	statement, err := database.Prepare(*preparedStatement)
	utils.CheckError(err)
	result, err := statement.Query()
	utils.CheckError(err)
	return result
}

//GetTrainingData returns all training data from the machine learning training table.
func GetTrainingData() *map[bayesian.Class]bin_utils.FunctionDetails {
	preparedStatement := fmt.Sprintf("SELECT * FROM %s", MLTrainingSetTableName)
	result := QueryDB(MLTrainingSetTableLocation, &preparedStatement)

	var functionDetailsArray []bin_utils.FunctionDetails

	for result.Next() {
		functionDetails := new(bin_utils.FunctionDetails)
		var primKey int
		var tokens string
		var entryPoint string

		result.Scan(&primKey, &functionDetails.FunctionName, &tokens, &entryPoint)

		functionDetails.LowAddress = entryPoint
		functionDetails.Tokens = strings.Fields(tokens)
		functionDetailsArray = append(functionDetailsArray, *functionDetails)
	}

	var classes map[bayesian.Class]bin_utils.FunctionDetails = make(map[bayesian.Class]bin_utils.FunctionDetails)
	for _, function := range functionDetailsArray {
		classes[bayesian.Class(function.FunctionName)] = function
	}
	return &classes
}

//GetDistinctBinaries returns all distinct binary file names from the database.
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

//GetSymbolTable returns the symbol table from the database of the binary name supplied.
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
		symbolTable.PopulateMap(&entryPoint, &functionName, &probability)
	}
	return symbolTable
}

//DelSymbolTable deletes the symbol table from the database associated with the binary name supplied.
func DelSymbolTable(binaryName *string) {
	var preparedStatement string = fmt.Sprintf("DELETE FROM %s WHERE %s=?", SymbolTablesTableName, BinaryNameColumn)
	err := deleteFromDBWithParameter(SymbolTablesTableLocation, &preparedStatement, binaryName)
	utils.CheckError(err)
}
