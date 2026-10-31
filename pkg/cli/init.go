package cli

import (
	"github.com/spf13/cobra"
	"os"
)

func NewInitCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "init",
		Short: "Scaffold a new .resolv workspace in the current repository",
		RunE: func(cmd *cobra.Command, args []string) error {
			return os.MkdirAll(".resolv", 0750)
		},
	}
	return cmd
}