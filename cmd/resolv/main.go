package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	_resolv "resolv/pkg/cli"
)

func main() {
	rootCmd := &cobra.Command{
		Use:   "resolv",
		Short: "Resolv - automated issue-resolution agent",
	}

	rootCmd.AddCommand(_resolv.NewInitCmd())
	rootCmd.AddCommand(_resolv.NewSetupCmd())
	rootCmd.AddCommand(_resolv.NewPipelineCmd())

	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}