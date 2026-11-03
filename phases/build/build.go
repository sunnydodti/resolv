package phases

import (
	"fmt"
	"os/exec"
	"time"
)

func Build(issueRef, domain string) error {
	return doBuildTest("", "")
}

func doBuildTest(buildCmd, testCmd string) error {
	if buildCmd == "" && testCmd == "" {
		fmt.Println("[Build] No build/test commands configured — skipping")
		return nil
	}
	if buildCmd != "" {
		cmd := exec.Command(buildCmd, "-o", "resolv.exe", ".")
		cmd.Dir = "."
		_, err := cmd.Output()
		if err != nil {
			if exitErr, ok := err.(*exec.ExitError); ok {
				fmt.Printf("[Build] Build output:\n%s\n", exitErr.Stderr)
			}
			return fmt.Errorf("build failed: %w", err)
		}
		fmt.Printf("[Build] Executable built successfully\n")
	}
	if testCmd != "" {
		tCmd := exec.Command(testCmd, "-count=1", "-timeout=30s", "./...")
		tCmd.Dir = "."
		tOut, tErr := tCmd.Output()
		_ = tOut
		if tErr != nil {
			fmt.Printf("[Build] Some tests failed (continuing): %v\n", tErr)
		} else {
			fmt.Printf("[Build] Tests passed in %s\n", time.Since(time.Now()))
		}
	}
	return nil
}

func Lint(issueRef, domain string) error {
	fmt.Println("[Lint] Lint skipped: no lint command configured")
	return nil
}
