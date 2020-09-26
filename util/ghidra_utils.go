package util

import (
	"fmt"
	"os/exec"
)

func StartGhidraAnalysis(fileName string) {
	var ghidraHeadless string = "/home/xenios/ghidra_9.1.2_PUBLIC/support/analyzeHeadless"
	var ghidraProjectLocation string = "\\/home/xenios/ghidra_projects"
	var ghidraProject string = "glyph"
	var ghidraScript string = "\\/home/xenios/ghidra_scripts/ClangTokenGenerator.java"

	err := exec.Command(ghidraHeadless, ghidraProjectLocation, ghidraProject, "-import", fileName, "-postScript", ghidraScript, "-overwrite", ">>", "test").Start()
	if err != nil {
		fmt.Println(err)
	}
}
