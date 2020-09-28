package dbutils

import (
	"database/sql"
	"fmt"
	"glyph/glyph/util"
)

func setupMLTrainingDB() {

	var directoryParent string = "../database"
	var directoryName string = "ml_training_set"
	_, err := util.CreateDirectory(directoryParent, directoryName)
	util.CheckError(err)

	database, err := sql.Open("sqlite3", MLTrainingSetTableLocation)
	defer database.Close()
	util.CheckError(err)
	preparedStatement := fmt.Sprintf("CREATE TABLE IF NOT EXISTS %s (id INTEGER PRIMARY KEY, %s TEXT, %s TEXT, %s TEXT)", MLTrainingSetTableName, LowAddressColumn, HighAddressColumn, TokensColumn)
	statement, err := database.Prepare(preparedStatement)
	util.CheckError(err)
	statement.Exec()
}

//SetupDB Sets up the web applications database.
func SetupDB() {
	fmt.Println("Setting up database...")
	setupMLTrainingDB()
	fmt.Println("Database setup complete!")
}
