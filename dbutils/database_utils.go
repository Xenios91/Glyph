package dbutils

import (
	"database/sql"
	"fmt"
	"glyph/glyph/util"

	_ "github.com/mattn/go-sqlite3"
)

//InsertDB Insert a record into the supplied table.
func InsertDB(tableName string, lowAddress string, highAddress string, tokens string) {
	database, err := sql.Open("sqlite3", mlTrainingSetTableLocation)
	defer database.Close()
	preparedStatement := fmt.Sprintf("INSERT INTO %s (%s, %s, %s) VALUES (?, ?, ?)", tableName, LowAddressColumn, HighAddressColumn, TokensColumn)
	statement, err := database.Prepare(preparedStatement)
	util.CheckError(err)
	result, err := statement.Exec(lowAddress, highAddress, tokens)
	util.CheckError(err)
	insertID, _ := result.LastInsertId()
	fmt.Printf("Function ID: %v inserted to %s with lowAddress of %s and highAddress of %s containing the following tokens: %s\n", insertID, tableName, lowAddress, highAddress, tokens)
}

func QueryDB(preparedStatement *string) *sql.Rows {
	database, err := sql.Open("sqlite3", mlTrainingSetTableLocation)
	defer database.Close()
	statement, err := database.Prepare(*preparedStatement)
	util.CheckError(err)
	result, err := statement.Query()
	util.CheckError(err)
	return result
}
