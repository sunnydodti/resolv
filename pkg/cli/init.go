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

			// Option A: split config / secrets
			// resolv.yml holds keys; credentials.json holds values (raw or env:VAR)
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
				// No token: empty reference list
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
			if len(creds) > 0 {
				b, _ := json.MarshalIndent(creds, "", "  ")
				if err := os.WriteFile(filepath.Join(dir, "credentials.json"), b, 0600); err != nil {
					return err
				}
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
