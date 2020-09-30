package dbutils

import (
	"database/sql"
	"fmt"
	"glyph/glyph/elftools"
	"glyph/glyph/util"
	"strings"
)

func createMLTrainingDB() {
	var directoryParent string = "../database"
	var directoryName string = "ml_training_set"
	_, err := util.CreateDirectory(directoryParent, directoryName)
	util.CheckError(err)

	database, err := sql.Open("sqlite3", mlTrainingSetTableLocation)
	defer database.Close()
	util.CheckError(err)
	preparedStatement := fmt.Sprintf("CREATE TABLE IF NOT EXISTS %s (id INTEGER PRIMARY KEY, %s TEXT, %s TEXT, %s TEXT)", MLTrainingSetTableName, LowAddressColumn, HighAddressColumn, TokensColumn)
	statement, err := database.Prepare(preparedStatement)
	util.CheckError(err)
	statement.Exec()
}

func loadTrainingData() {
	preparedStatement := fmt.Sprintf("SELECT * FROM %s", MLTrainingSetTableName)
	result := QueryDB(&preparedStatement)
	var functionDetailsArray []elftools.FunctionDetails

	for result.Next() {
		functionDetails := new(elftools.FunctionDetails)
		var primKey int
		var tokens string

		result.Scan(&primKey, &functionDetails.LowAddress, &functionDetails.HighAddress, &tokens)

		functionDetails.Tokens = strings.Fields(tokens)
		functionDetailsArray = append(functionDetailsArray, *functionDetails)
	}
}

//SetupDB Sets up the web applications database.
func SetupDB() {
	fmt.Println("Setting up database...")
	if util.CheckIfFileExist(mlTrainingSetTableLocation) {
		loadTrainingData()
	} else {
		createMLTrainingDB()
	}

	fmt.Println("Database setup complete!")
}
