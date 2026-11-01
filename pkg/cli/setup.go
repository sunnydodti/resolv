package cli

import (
	"bufio"
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
	_resolv "resolv/pkg/config"
)

func NewSetupCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "setup [domain_name]",
		Short: "Setup a domain with repos and API keys",
		Args:  cobra.MaximumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			domainName := ""
			if len(args) > 0 && args[0] != "" {
				domainName = args[0]
			}

			// Read existing configs (read-only at start)
			domainCfg, err := _resolv.LoadDomainConfig()
			if err != nil {
				domainCfg = &_resolv.DomainConfig{Domains: map[string]_resolv.DomainEntry{}}
			}
			if domainCfg.Domains == nil {
				domainCfg.Domains = map[string]_resolv.DomainEntry{}
			}

			creds, err := _resolv.LoadCredentials()
			if err != nil {
				creds = map[string]string{}
			}

			// Prompt domain if not given
			if domainName == "" {
				fmt.Fprint(cmd.OutOrStderr(), "Domain name: ")
				scanner := bufio.NewScanner(os.Stdin)
				if scanner.Scan() {
					domainName = strings.TrimSpace(scanner.Text())
				}
			}
			if domainName == "" {
				return fmt.Errorf("domain name required")
			}

			// Get or create domain entry
			domainEntry, exists := domainCfg.Domains[domainName]
			if !exists {
				domainEntry = _resolv.DomainEntry{
					Repos: map[string][]_resolv.Repo{},
				}
			}

			// Interactive menu: add repos
			for {
				fmt.Fprintln(cmd.OutOrStderr(), "\nRepo type to add (primary/reference/other, or done):")
				fmt.Fprint(cmd.OutOrStderr(), "Choice: ")
				scanner := bufio.NewScanner(os.Stdin)
				if !scanner.Scan() {
					break
				}
				repoType := strings.TrimSpace(scanner.Text())
				if repoType == "done" || repoType == "" {
					break
				}
				if repoType != "primary" && repoType != "reference" && repoType != "other" {
					fmt.Fprintln(cmd.OutOrStderr(), "Invalid type. Use primary/reference/other.")
					continue
				}

				fmt.Fprintf(cmd.OutOrStderr(), "Source [github]: ")
				scanner.Scan()
				source := strings.TrimSpace(scanner.Text())
				if source == "" {
					source = "github"
				}

				fmt.Fprintf(cmd.OutOrStderr(), "Base path [github.com]: ")
				scanner.Scan()
				base := strings.TrimSpace(scanner.Text())
				if base == "" {
					base = "github.com"
				}

				fmt.Fprintf(cmd.OutOrStderr(), "Repo path: ")
				scanner.Scan()
				repoPath := strings.TrimSpace(scanner.Text())
				if repoPath == "" {
					fmt.Fprintln(cmd.OutOrStderr(), "Repo path required")
					continue
				}

				// API key: list existing keys or ask for new name
				selectedKey := ""
				if len(creds) > 0 {
					fmt.Fprintln(cmd.OutOrStderr(), "\nExisting keys:")
					for k := range creds {
						fmt.Fprintf(cmd.OutOrStderr(), "  %s\n", k)
					}
					fmt.Fprintf(cmd.OutOrStderr(), "Select key number (or press Enter to enter new): ")
					scanner.Scan()
					input := strings.TrimSpace(scanner.Text())
					if input != "" {
						var idx int
						if _, err := fmt.Sscanf(input, "%d", &idx); err == nil && idx > 0 && idx <= len(creds) {
							keys := make([]string, 0, len(creds))
							for k := range creds {
								keys = append(keys, k)
							}
							selectedKey = keys[idx-1]
						} else {
							selectedKey = input
						}
					}
				}
				if selectedKey == "" {
					fmt.Fprintf(cmd.OutOrStderr(), "Enter API key name (or env:VAR, or Enter to skip): ")
					scanner.Scan()
					keyInput := strings.TrimSpace(scanner.Text())
					if keyInput != "" {
						selectedKey = keyInput
					}
				}

				// Store key if new (avoid overwrite)
				if selectedKey != "" {
					if _, exists := creds[selectedKey]; !exists {
						// Ask for value only if key is new
						fmt.Fprintf(cmd.OutOrStderr(), "Enter value for %s (raw or env:VAR): ", selectedKey)
						scanner.Scan()
						val := strings.TrimSpace(scanner.Text())
						if val != "" {
							creds[selectedKey] = val
						}
					} else {
						fmt.Fprintf(cmd.OutOrStderr(), "Key %q already exists (not overwritten)\n", selectedKey)
					}
				}

				// Add repo to domain entry
				repo := _resolv.Repo{
					Source:   source,
					BasePath: base,
					RepoPath: repoPath,
				}
				if domainEntry.Repos == nil {
					domainEntry.Repos = map[string][]_resolv.Repo{}
				}
				domainEntry.Repos[repoType] = append(domainEntry.Repos[repoType], repo)

				fmt.Fprintln(cmd.OutOrStderr(), "Added.")
			}

			// Save
			domainCfg.Domains[domainName] = domainEntry
			if err := _resolv.SaveDomainConfig(domainCfg); err != nil {
				return err
			}
			if len(creds) > 0 {
				if err := _resolv.SaveCredentials(creds); err != nil {
					return err
				}
			}

			fmt.Fprintf(cmd.OutOrStderr(), "Domain %q saved.\n", domainName)
			return nil
		},
	}
	return cmd
}