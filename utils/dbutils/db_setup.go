package glyph

import (
	"database/sql"
	"fmt"
	utils "glyph/glyph/utils"
)

func createMLTrainingDB() {
	var directoryParent string = "./database"
	var directoryName string = "ml_training_set"
	_, err := utils.CreateDirectory(directoryParent, directoryName)
	utils.CheckError(err)

	database, err := sql.Open("sqlite3", MLTrainingSetTableLocation)
	defer database.Close()
	utils.CheckError(err)
	preparedStatement := fmt.Sprintf("CREATE TABLE IF NOT EXISTS %s (id INTEGER PRIMARY KEY, %s TEXT, %s TEXT)", MLTrainingSetTableName, FunctionNameColumn, TokensColumn)
	statement, err := database.Prepare(preparedStatement)
	utils.CheckError(err)
	statement.Exec()
}

func createSymbolTablesDB() {
	var directoryParent string = "./database"
	var directoryName string = "symbol_tables"
	_, err := utils.CreateDirectory(directoryParent, directoryName)
	utils.CheckError(err)

	database, err := sql.Open("sqlite3", SymbolTablesTableLocation)
	defer database.Close()
	utils.CheckError(err)
	preparedStatement := fmt.Sprintf("CREATE TABLE IF NOT EXISTS %s (id INTEGER PRIMARY KEY, %s TEXT, %s TEXT, %s TEXT, %s TEXT)", SymbolTablesTableName, BinaryNameColumn, EntryPointColumn, FunctionNameColumn, ProbabilityColumn)
	statement, err := database.Prepare(preparedStatement)
	utils.CheckError(err)
	statement.Exec()
}

//SetupDB Sets up the web applications database.
func SetupDB() {
	fmt.Print("Setting up database... ")
	if !utils.CheckIfFileExist(MLTrainingSetTableLocation) {
		createMLTrainingDB()
	}
	if !utils.CheckIfFileExist(SymbolTablesTableLocation) {
		createSymbolTablesDB()
	}
	fmt.Println("Database setup complete!")
}
