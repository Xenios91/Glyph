package elftools

import (
	"fmt"
)

//FunctionDetails A struct that consist of the starting and ending address of a function as well as all tokens associated with it.
type FunctionDetails struct {
	LowAddress  string   `json:"lowAddress"`
	HighAddress string   `json:"highAddress"`
	Tokens      []string `json:"tokenList"`
}

//FunctionDetailsArray A struct of 2 arrays, ErroredFunctions and Functions.
type FunctionDetailsArray struct {
	BinaryName       string            `json:"binaryName"`
	ErroredFunctions []FunctionDetails `json:"erroredFunctions"`
	Functions        []FunctionDetails `json:"functions"`
}

//ProcessFunctionDetailsArray Processes a FunctionDetailsArray struct.
func (functionDetailsArray FunctionDetailsArray) ProcessFunctionDetailsArray() {
	var functions []FunctionDetails = functionDetailsArray.Functions
	var erroredFunctions []FunctionDetails = functionDetailsArray.ErroredFunctions

	for _, function := range functions {
		fmt.Printf("Function found: \nStarting at %s \nEnding at %s\n Tokens:%s\n\n", function.LowAddress, function.HighAddress, function.Tokens)
	}

	for _, erroredFunction := range erroredFunctions {
		fmt.Printf("Errored function: \nStarting at %s \nEnding at %s\n Tokens:%s\n\n", erroredFunction.LowAddress, erroredFunction.HighAddress, erroredFunction.Tokens)
	}
}
