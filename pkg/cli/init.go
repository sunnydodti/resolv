package cli

import (
	"encoding/json"
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
			if err := os.RemoveAll(dir); err != nil {
				fmt.Fprintf(cmd.OutOrStderr(), "Warning: could not remove %q: %v\n", dir, err)
			}
			if err := os.MkdirAll(dir, 0750); err != nil {
				return err
			}

			fmt.Fprint(cmd.OutOrStderr(), "Enter github token or env:GITHUB_TOKEN (Enter to skip): ")
			var token string
			fmt.Scanln(&token)

			creds := map[string]string{}
			if token != "" {
				creds["github"] = token
			}

			resolvYaml := `version: "1.0"
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
tokens:
  github:
    - "github"
`
			if token == "" {
				resolvYaml = `version: "1.0"
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
tokens: {}
`
		}

			if err := os.WriteFile(filepath.Join(dir, "resolv.yml"), []byte(resolvYaml), 0644); err != nil {
				return err
			}
			if len(creds) > 0 {
				b, err := json.MarshalIndent(creds, "", "  ")
				if err != nil {
					return err
				}
				if err := os.WriteFile(filepath.Join(dir, "credentials.json"), b, 0600); err != nil {
					return err
				}
			}
			fmt.Fprintln(cmd.OutOrStderr(), "Resolv: initialized config directory at", dir)
			return nil
		},
	}
	return cmd
}
