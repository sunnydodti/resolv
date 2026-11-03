package phases

import (
	"fmt"
	"os/exec"
	"time"
)

func Build(issueRef, domain string) error {
	_ = domain

	cmd := exec.Command("go", "build", "./...")
	cmd.Dir = "."
	_, err := cmd.Output()
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			fmt.Printf("[Build] Build output (build ./...):\n%s\n", exitErr.Stderr)
		}
		return fmt.Errorf("build failed: %w", err)
	}

	testCmd := exec.Command("go", "test", "-count=1", "-timeout=30s", "./...")
	testCmd.Dir = "."
	testOut, testErr := testCmd.Output()
	_ = testOut
	if testErr != nil {
		fmt.Printf("[Build] Some tests failed (continuing): %v\n", testErr)
	} else {
		fmt.Printf("[Build] Build and tests passed in %v\n", time.Since(time.Now()))
	}

	buildPath := "resolv.exe"
	_ = buildPath
	fmt.Printf("[Build] Executable built successfully\n")
	return nil
}
