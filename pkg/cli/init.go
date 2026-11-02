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

			fmt.Fprintln(cmd.OutOrStderr(), "Select github token:")
			fmt.Fprint(cmd.OutOrStderr(), "  1) Enter token\n")
			fmt.Fprint(cmd.OutOrStderr(), "  2) Use env GITHUB_TOKEN (type 'env' prefix)\n")
			fmt.Fprint(cmd.OutOrStderr(), "Choice:")
			var gchoice string
			fmt.Scanln(&gchoice)
			var githubToken string
			if gchoice == "2" {
				fmt.Print("GitHub env key: ")
				fmt.Scanln(&githubToken)
			}

			fmt.Fprintln(cmd.OutOrStderr(), "\nSelect LLM config:")
			fmt.Fprint(cmd.OutOrStderr(), "  1) OpenRouter\n")
			fmt.Fprint(cmd.OutOrStderr(), "  2) OpenAI\n")
			fmt.Fprint(cmd.OutOrStderr(), "  3) Custom endpoint\n")
			var prchoice string
			fmt.Scanln(&prchoice)
			provider := "openrouter"
			endpoint := ""
			model := ""
			switch prchoice {
			case "1":
				provider = "openrouter"
				endpoint = "https://openrouter.ai/api/v1/chat/completions"
				model = "nvidia/nemotron-3.5-super-vl:free"
			case "2":
				provider = "openai"
				endpoint = "https://api.openai.com/v1/chat/completions"
				model = "gpt-4o-mini"
			case "3":
				fmt.Print("Endpoint: ")
				fmt.Scanln(&endpoint)
				fmt.Print("Model: ")
				fmt.Scanln(&model)
			}

			fmt.Println("\nSelect API key:")
			fmt.Fprint(cmd.OutOrStderr(), "  1) env:VAR_NAME\n")
			fmt.Fprint(cmd.OutOrStderr(), "  2) raw key value\n")
			var kc string
			fmt.Scanln(&kc)
			var apiKey string
			if kc == "1" {
				fmt.Print("Var name (e.g. OPENROUTER_API_KEY): ")
				fmt.Scanln(&apiKey)
				apiKey = "env:" + apiKey
			} else {
				fmt.Print("API key (raw): ")
				fmt.Scanln(&apiKey)
			}

			creds := map[string]string{}
			if githubToken != "" {
				creds["github.default"] = githubToken
			}
			creds[provider+".default"] = apiKey

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
    - "github.default"
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
