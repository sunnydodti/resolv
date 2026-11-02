package cli

import "github.com/spf13/cobra"

func NewPipelineCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "resolv [issue_reference]",
		Short: "Run the autonomous resolution pipeline",
		Args:  cobra.MaximumNArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			cmd.Println("Pipeline: not yet wired (needs phase/agent wiring)")
		},
	}
	cmd.Flags().String("domain", "", "CSV domain list")
	cmd.Flags().Bool("analysis-only", false, "Stop after plan")
	cmd.Flags().Bool("resume", false, "Resume from session")
	cmd.Flags().Bool("dry-run", false, "Skip publish")
	cmd.Flags().Bool("verbose", false, "Verbose logging")
	cmd.Flags().Int("max-healing-turns", 3, "Self-healing budget")
	return cmd
}
