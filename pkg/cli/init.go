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
			if err := os.MkdirAll(dir, 0750); err != nil {
				return err
			}

			fmt.Fprint(cmd.OutOrStderr(), "Enter github token or env:GITHUB_TOKEN (Enter to skip): ")
			var githubToken string
			fmt.Scanln(&githubToken)

			fmt.Fprint(cmd.OutOrStderr(), "LLM endpoint (Enter for openai default): ")
			var endpoint string
			fmt.Scanln(&endpoint)
			if endpoint == "" {
				endpoint = "https://api.openai.com/v1/chat/completions"
			}

			fmt.Fprint(cmd.OutOrStderr(), "LLM model (Enter for gpt-4o-mini): ")
			var model string
			fmt.Scanln(&model)
			if model == "" {
				model = "gpt-4o-mini"
			}

			fmt.Fprint(cmd.OutOrStderr(), "LLM API key (raw value or env:VAR): ")
			var apiKey string
			fmt.Scanln(&apiKey)

			creds := map[string]string{}
			if githubToken != "" {
				creds["github"] = githubToken
			}
			creds[model] = apiKey

			resolvYaml := fmt.Sprintf(`version: "1.0"
project:
  name: "resolv"
  endpoint: "%s"
  model: "%s"
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
`, endpoint, model)

			if err := os.WriteFile(filepath.Join(dir, "resolv.yml"), []byte(resolvYaml), 0644); err != nil {
				return err
			}
			if len(creds) > 0 {
				b, err := json.MarshalIndent(creds, "", "  ")
				if err != nil {
					return err
				}
				if err := os.WriteFile(filepath.Join(dir, "credentials.json"), b, 0644); err != nil {
					return err
				}
			}

			fmt.Fprintln(cmd.OutOrStderr(), "\nResolv: initialized config at", dir)
			return nil
		},
	}
	return cmd
}