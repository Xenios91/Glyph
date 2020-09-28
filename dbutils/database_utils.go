package dbutils

import (
	"database/sql"
	"glyph/glyph/util"

	_ "github.com/mattn/go-sqlite3"
)

//SetupDB Sets up the web applications database.
func SetupDB() {
	var directoryParent string = "../database"
	var directoryName string = "ml_training_set"

	dirPath, err := util.CreateDirectory(directoryParent, directoryName)
	util.CheckError(err)
	dbLocation := *dirPath + "/glyph_ml_training_set.db"
	database, _ := sql.Open("sqlite3", dbLocation)
	statement, _ := database.Prepare("CREATE TABLE IF NOT EXISTS ML_Training_Sets (id INTEGER PRIMARY KEY, lowAddress TEXT, highAddress TEXT, tokens TEXT)")
	statement.Exec()
}
