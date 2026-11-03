package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	_resolv "resolv/pkg/cli"
	"resolv/pkg/pipeline"
)

func main() {
	rootCmd := &cobra.Command{
		Use:   "resolv [issue_reference]",
		Short: "Resolv - automated issue-resolution agent",
		Args:  cobra.MaximumNArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			issue := ""
			if len(args) > 0 {
				issue = args[0]
			}
			domain, _ := cmd.Flags().GetString("domain")
			analysisOnly, _ := cmd.Flags().GetBool("analysis-only")
			resume, _ := cmd.Flags().GetBool("resume")
			dryRun, _ := cmd.Flags().GetBool("dry-run")
			verbose, _ := cmd.Flags().GetBool("verbose")
			maxTurns, _ := cmd.Flags().GetInt("max-healing-turns")
			_ = analysisOnly
			fsm := pipeline.FSM{}
			if err := fsm.Run(issue, domain, resume, dryRun, verbose, maxTurns); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
		},
	}
	rootCmd.Flags().String("domain", "", "CSV domain list")
	rootCmd.Flags().Bool("analysis-only", false, "Only analyze/plan")
	rootCmd.Flags().Bool("resume", false, "Resume from session")
	rootCmd.Flags().Bool("dry-run", false, "Skip publish")
	rootCmd.Flags().Bool("verbose", false, "Verbose")
	rootCmd.Flags().Int("max-healing-turns", 3, "Budget")

	rootCmd.AddCommand(_resolv.NewInitCmd())
	rootCmd.AddCommand(_resolv.NewSetupCmd())

	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
