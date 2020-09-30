package elftools

type FunctionDetails struct {
	LowAddress  string   `json:"lowAddress"`
	HighAddress string   `json:"highAddress"`
	Tokens      []string `json:"tokenList"`
}

type erroredFunctionDetails struct {
	LowAddress  string   `json:"lowAddress"`
	HighAddress string   `json:"highAddress"`
	Tokens      []string `json:"tokenList"`
}

//BinaryDetails A structure of details about an analyzed binary.
type BinaryDetails struct {
	BinaryName   string `json:"binaryName"`
	FunctionsMap struct {
		FunctionDetails         []FunctionDetails        `json:"functions"`
		ErroredFunctionsDetails []erroredFunctionDetails `json:"erroredFunctions"`
	} `json:"functionsMap"`
}
