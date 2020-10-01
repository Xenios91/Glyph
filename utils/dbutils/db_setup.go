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

	database, err := sql.Open("sqlite3", mlTrainingSetTableLocation)
	defer database.Close()
	utils.CheckError(err)
	preparedStatement := fmt.Sprintf("CREATE TABLE IF NOT EXISTS %s (id INTEGER PRIMARY KEY, %s TEXT, %s TEXT, %s TEXT, %s TEXT)", MLTrainingSetTableName, FunctionNameColumn, LowAddressColumn, HighAddressColumn, TokensColumn)
	statement, err := database.Prepare(preparedStatement)
	utils.CheckError(err)
	statement.Exec()
}

//SetupDB Sets up the web applications database.
func SetupDB() {
	fmt.Print("Setting up database... ")
	if !utils.CheckIfFileExist(mlTrainingSetTableLocation) {
		createMLTrainingDB()
	}
	fmt.Println("Database setup complete!")
}
