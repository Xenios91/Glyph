package elf_tools

type FunctionDetails struct {
	LowAddress  string   `json:"lowAddress"`
	HighAddress string   `json:"highAddress"`
	Tokens      []string `json:"tokenList"`
}

type FunctionDetailsArray struct {
	ErroredFunctions []struct {
		HighAddress string   `json:"highAddress"`
		LowAddress  string   `json:"lowAddress"`
		TokenList   []string `json:"tokenList"`
	} `json:"erroredFunctions"`
	Functions []struct {
		HighAddress string   `json:"highAddress"`
		LowAddress  string   `json:"lowAddress"`
		TokenList   []string `json:"tokenList"`
	} `json:"functions"`
}
