package elf_tools

type FunctionDetails struct {
	LowAddress  string   `json:"lowAddress"`
	HighAddress string   `json:"highAddress"`
	Tokens      []string `json:"tokenList"`
}
