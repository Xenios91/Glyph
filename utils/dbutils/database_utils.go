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
func InsertDB(tableName string, functionName string, lowAddress string, highAddress string, tokens string) {
	database, err := sql.Open("sqlite3", mlTrainingSetTableLocation)
	defer database.Close()
	preparedStatement := fmt.Sprintf("INSERT INTO %s (%s, %s, %s, %s) VALUES (?, ?, ?, ?)", tableName, FunctionNameColumn, LowAddressColumn, HighAddressColumn, TokensColumn)
	statement, err := database.Prepare(preparedStatement)
	utils.CheckError(err)
	result, err := statement.Exec(functionName, lowAddress, highAddress, tokens)
	utils.CheckError(err)
	insertID, _ := result.LastInsertId()
	fmt.Printf("Function ID: %v inserted to %s with lowAddress of %s and highAddress of %s containing the following tokens: %s\n", insertID, tableName, lowAddress, highAddress, tokens)
}

func QueryDB(preparedStatement *string) *sql.Rows {
	database, err := sql.Open("sqlite3", mlTrainingSetTableLocation)
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
