package cli

import (
	"github.com/spf13/cobra"
	"resolv/pkg/pipeline"
)

func NewPipelineCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "pipeline [issue_reference]",
		Short: "Run the autonomous resolution pipeline",
		Args:  cobra.MaximumNArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			issue := ""
			if len(args) > 0 { issue = args[0] }
			domain, _ := cmd.Flags().GetString("domain")
			analysisOnly, _ := cmd.Flags().GetBool("analysis-only")
			resume, _ := cmd.Flags().GetBool("resume")
			dryRun, _ := cmd.Flags().GetBool("dry-run")
			verbose, _ := cmd.Flags().GetBool("verbose")
			maxTurns, _ := cmd.Flags().GetInt("max-healing-turns")
			_ = analysisOnly
			fsm := pipeline.FSM{}
			_ = fsm.Run(issue, domain, resume, dryRun, verbose, maxTurns)
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
