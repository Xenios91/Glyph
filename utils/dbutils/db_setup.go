package glyph

import (
	"database/sql"
	"fmt"
	utils "glyph/glyph/utils"
	"sync"
)

var once sync.Once

func createMLTrainingDB() {
	var directoryParent string = "./database"
	var directoryName string = "ml_training_set"
	_, err := utils.CreateDirectory(&directoryParent, &directoryName)
	utils.CheckError(err)

	database, err := sql.Open("sqlite3", MLTrainingSetTableLocation)
	defer database.Close()
	utils.CheckError(err)
	preparedStatement := fmt.Sprintf("CREATE TABLE IF NOT EXISTS %s (id INTEGER PRIMARY KEY, %s TEXT, %s TEXT, %s TEXT)", MLTrainingSetTableName, FunctionNameColumn, TokensColumn, EntryPointColumn)
	statement, err := database.Prepare(preparedStatement)
	utils.CheckError(err)
	statement.Exec()
}

func createSymbolTablesDB() {
	var directoryParent string = "./database"
	var directoryName string = "symbol_tables"
	_, err := utils.CreateDirectory(&directoryParent, &directoryName)
	utils.CheckError(err)

	database, err := sql.Open("sqlite3", SymbolTablesTableLocation)
	defer database.Close()
	utils.CheckError(err)
	preparedStatement := fmt.Sprintf("CREATE TABLE IF NOT EXISTS %s (id INTEGER PRIMARY KEY, %s TEXT, %s TEXT, %s TEXT, %s TEXT)", SymbolTablesTableName, BinaryNameColumn, EntryPointColumn, FunctionNameColumn, ProbabilityColumn)
	statement, err := database.Prepare(preparedStatement)
	utils.CheckError(err)
	statement.Exec()
}

//SetupDB Sets up the web applications database, can only be run once.
func SetupDB() {
	once.Do(func() {
		fmt.Print("Setting up database... ")
		if !utils.CheckIfFileExist(MLTrainingSetTableLocation) {
			fmt.Print("Creating machine learning training database...")
			createMLTrainingDB()
		}
		if !utils.CheckIfFileExist(SymbolTablesTableLocation) {
			fmt.Print("Creating symbol table database...")
			createSymbolTablesDB()
		}
		fmt.Println("Database setup complete!")
	})

}
