package cli

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
	_resolv "resolv/pkg/config"
)

func NewInitCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "init",
		Short: "Scaffold a new Resolv workspace",
		RunE: func(cmd *cobra.Command, args []string) error {
			dir := _resolv.ConfigDir()
			// Remove existing directory so we always recreate
			os.RemoveAll(dir)
			if err := os.MkdirAll(dir, 0750); err != nil {
				return err
			}

			// Prompt for global token (no env assumptions)
			fmt.Fprint(cmd.OutOrStderr(), "Enter global token (press Enter to skip): ")
			var token string
			fmt.Scanln(&token)

			const resolvResolv = `version: "1.0"
project:
  name: "resolv"
execution:
  max_iterations: 4
  execution_timeout: 300
telemetry:
  enabled: true
  audit_log_path: ".resolv/audit.log"
platforms:
  - github
model:
  credential_key: "%s"
`
			resolvYaml := fmt.Sprintf(resolvResolv, token)

			domainYaml := `domain:
  repos:
    primary:
      - source: "github"
        base_path: "github.com"
        repo_path: "org/repo"
    reference:
      - source: "gitlab"
        base_path: "gitlab.com"
        repo_path: "group/project"
    other:
      - source: "self-hosted"
        base_path: "https://git.mycompany.com"
        repo_path: "team/repo"
`
			if err := os.WriteFile(filepath.Join(dir, "resolv.yml"), []byte(resolvYaml), 0644); err != nil {
				return err
			}
			if err := os.WriteFile(filepath.Join(dir, "domain.yml"), []byte(domainYaml), 0644); err != nil {
				return err
			}
			fmt.Fprintln(cmd.OutOrStderr(), "Resolv: initialized config directory at", dir)
			return nil
		},
	}
	return cmd
}