package glyph

//CheckError checks if an error supplied is nil, if not it will panic.
func CheckError(err error) {
	if err != nil {
		panic(err)
	}
}
