package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
	_resolv "resolv/pkg/config"
)

var providers = []string{"openrouter", "anthropic", "google", "mistral", "deepseek", "ollama"}

type initState struct {
	Provider     string `json:"provider"`
	Endpoint     string `json:"endpoint"`
	Model        string `json:"model"`
	GitHubToken  string `json:"githubToken"`
	APIKey       string `json:"apiKey"`
}

func NewInitCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "init",
		Short: "Scaffold a new Resolv workspace",
		RunE: func(cmd *cobra.Command, args []string) error {
			dir := _resolv.ConfigDir()
			_ = os.MkdirAll(dir, 0750)

			prev := initState{}
			prevFile, err := os.ReadFile(filepath.Join(dir, "init_prev.json"))
			if err == nil {
				_ = json.Unmarshal(prevFile, &prev)
			}

			fmt.Fprintln(cmd.OutOrStderr(), "Available providers:")
			for i, p := range providers {
				fmt.Fprintf(cmd.OutOrStderr(), "  %d - %s\n", i+1, p)
			}

			fmt.Fprintf(cmd.OutOrStderr(), "\nPrevious values (press Enter to keep):\n")
			fmt.Fprintf(cmd.OutOrStderr(), "  Provider: %s\n", prevValueStr(prev.Provider, "(empty)"))
			fmt.Fprintf(cmd.OutOrStderr(), "  Endpoint: %s\n", prevValueStr(prev.Endpoint, "(empty)"))
			fmt.Fprintf(cmd.OutOrStderr(), "  Model: %s\n", prevValueStr(prev.Model, "(empty)"))

			selectedProvider := prev.Provider
			fmt.Fprint(cmd.OutOrStderr(), "Enter provider number (Enter=keep previous): ")
			var choiceStr string
			fmt.Scanln(&choiceStr)
			if choiceStr != "" {
				n := atoiSafe(choiceStr)
				if n >= 1 && n <= len(providers) {
					selectedProvider = providers[n-1]
				}
			}

			fmt.Fprintf(cmd.OutOrStderr(), "\nProvider selected: %s (confirmed)\n", selectedProvider)

			endpoint := prev.Endpoint
			if endpoint == "" || selectedProvider != prev.Provider {
				switch selectedProvider {
				case "openrouter": endpoint = "https://openrouter.ai/api/v1/chat/completions"
				case "google": endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
				case "anthropic": endpoint = "https://api.anthropic.com/v1/messages"
				case "mistral": endpoint = "https://api.mistral.ai/v1/chat/completions"
				case "deepseek": endpoint = "https://api.deepseek.com/chat/completions"
				case "ollama": endpoint = "http://localhost:11434/v1/chat/completions"
				default: endpoint = "https://openrouter.ai/api/v1/chat/completions"
				}
			}

			model := prev.Model
			if model == "" || selectedProvider != prev.Provider {
				switch selectedProvider {
				case "openrouter": model = "nvidia/nemotron-3-ultra-550b-a55b:free"
				case "google": model = "gemini-1.5-flash"
				case "anthropic": model = "claude-3-5-sonnet-20240620"
				case "mistral": model = "mistral-small"
				case "deepseek": model = "deepseek-chat"
				case "ollama": model = "llama3.1"
				default: model = "openai/gpt-4o-mini"
				}
			}

			fmt.Fprintf(cmd.OutOrStderr(), "Model (Confirm previous %s, Enter=keep): %s\n", prevValueStr(prev.Model, "(empty)"), model)
			fmt.Fprint(cmd.OutOrStderr(), "New model or Enter to confirm: ")
			var modelInput string
			fmt.Scanln(&modelInput)
			if modelInput != "" {
				model = modelInput
			}

			githubToken := prev.GitHubToken
			apiKey := prev.APIKey

			fmt.Fprintf(cmd.OutOrStderr(), "GitHub token (Enter to keep previous %s):\n", prevValueStr(prev.GitHubToken, "(empty)"))
			fmt.Fprint(cmd.OutOrStderr(), "Token value: ")
			var ghInput string
			fmt.Scanln(&ghInput)
			if ghInput != "" {
				githubToken = ghInput
			}

			fmt.Fprintf(cmd.OutOrStderr(), "LLM API key (Enter to keep previous %s): %s\n", selectedProvider, prevValueStr(prev.APIKey, "(empty)"))
			fmt.Fprint(cmd.OutOrStderr(), "Key value (raw or env:VAR): ")
			var keyInput string
			fmt.Scanln(&keyInput)
			if keyInput != "" {
				apiKey = keyInput
			}

			creds := map[string]string{}
			if githubToken != "" {
				creds["github"] = githubToken
			}
			switch selectedProvider {
			case "openrouter":
				creds["openrouter"] = apiKey
			case "google":
				creds["google"] = apiKey
			case "anthropic":
				creds["anthropic"] = apiKey
			default:
				creds[selectedProvider] = apiKey
			}

			resolvYaml := fmt.Sprintf(`version: "1.0"
project:
  name: "resolv"
  endpoint: "%s"
  model: "%s"
  provider: "%s"
  build_cmd: "go build ./..."
  test_cmd: "go test ./..."
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
`, endpoint, model, selectedProvider)

			_ = os.WriteFile(filepath.Join(dir, "resolv.yml"), []byte(resolvYaml), 0644)
			if len(creds) > 0 {
				b, _ := json.MarshalIndent(creds, "", "  ")
				_ = os.WriteFile(filepath.Join(dir, "credentials.json"), b, 0644)
			}

			saved := initState{
				Provider:     selectedProvider,
				Endpoint:     endpoint,
				Model:        model,
				GitHubToken:  githubToken,
				APIKey:       apiKey,
			}
			b, _ := json.MarshalIndent(saved, "", "  ")
			_ = os.WriteFile(filepath.Join(dir, "init_prev.json"), b, 0644)

			fmt.Fprintln(cmd.OutOrStderr(), "\nResolv: initialized at", dir, "provider=", selectedProvider)
			return nil
		},
	}
	return cmd
}

func prevValueStr(s string, emptyStr string) string {
	if s == "" || s == "(empty)" {
		return emptyStr
	}
	return s
}

func atoiSafe(s string) int {
	n := 0
	for _, ch := range s {
		if ch < '0' || ch > '9' {
		return -1
		}
		n = n*10 + int(ch-'0')
	}
	return n
}