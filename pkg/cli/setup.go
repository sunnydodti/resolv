package cli

import (
	"bufio"
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/spf13/cobra"
	_resolv "resolv/pkg/config"
)

func urlParseRepo(input string) (_resolv.Repo, bool) {
	if !strings.HasPrefix(input, "https://") {
		return _resolv.Repo{}, false
	}
	u, err := url.Parse(input)
	if err != nil {
		return _resolv.Repo{}, false
	}
	host := u.Host
	repoPath := strings.TrimPrefix(u.Path, "/")
	if host == "github.com" || host == "gitlab.com" || strings.Contains(host, "github") {
		return _resolv.Repo{
			Source:   "github",
			BasePath: "github.com",
			RepoPath: repoPath,
		}, true
	}
	if host == "gitlab.com" || strings.Contains(host, "gitlab") {
		return _resolv.Repo{
			Source:   "gitlab",
			BasePath: "gitlab.com",
			RepoPath: repoPath,
		}, true
	}
	return _resolv.Repo{
		Source:   "other",
		BasePath: input,
		RepoPath: repoPath,
	}, true
}

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

			domainEntry, err := _resolv.LoadDomainEntry(domainName)
			if err != nil {
				domainEntry = &_resolv.DomainEntry{Repos: map[string][]_resolv.Repo{}}
			}
			if domainEntry.Repos == nil {
				domainEntry.Repos = map[string][]_resolv.Repo{}
			}

			creds, err := _resolv.LoadCredentials()
			if err != nil {
				creds = map[string]string{}
			}

			for {
				fmt.Fprintln(cmd.OutOrStderr(), "\nRepo type (1=primary, 2=reference, 3=other, 4=done):")
				fmt.Fprint(cmd.OutOrStderr(), "Choice: ")
				scanner := bufio.NewScanner(os.Stdin)
				if !scanner.Scan() {
					break
				}
				choice := strings.TrimSpace(scanner.Text())
				if choice == "4" || choice == "done" || choice == "" {
					break
				}

				repoType := ""
				switch choice {
				case "1":
					repoType = "primary"
				case "2":
					repoType = "reference"
				case "3":
					repoType = "other"
				default:
					fmt.Fprintln(cmd.OutOrStderr(), "Invalid choice. Use 1/2/3/4.")
					continue
				}

				fmt.Fprintln(cmd.OutOrStderr(), "Paste URL (https://...) or enter repo details (Enter to skip URL):")
				fmt.Fprint(cmd.OutOrStderr(), "Repo: ")
				scanner.Scan()
				input := strings.TrimSpace(scanner.Text())

				var repo _resolv.Repo
				if input != "" {
					if r, ok := urlParseRepo(input); ok {
						repo = r
						fmt.Fprintln(cmd.OutOrStderr(), "Parsed URL -> source:", repo.Source, "base:", repo.BasePath, "repo:", repo.RepoPath)
					} else {
						// Treat as repo path
						repo = _resolv.Repo{Source: "github", BasePath: "github.com", RepoPath: input}
					}
				} else {
					fmt.Fprintf(cmd.OutOrStderr(), "Source (github/gitlab/other) [github]: ")
					scanner.Scan()
					source := strings.TrimSpace(scanner.Text())
					if source == "" {
						source = "github"
					}
					repo.Source = source

					fmt.Fprintf(cmd.OutOrStderr(), "Base path [github.com]: ")
					scanner.Scan()
					base := strings.TrimSpace(scanner.Text())
					if base == "" {
						base = "github.com"
					}
					repo.BasePath = base

					fmt.Fprintf(cmd.OutOrStderr(), "Repo path: ")
					scanner.Scan()
					repo.RepoPath = strings.TrimSpace(scanner.Text())
					if repo.RepoPath == "" {
						fmt.Fprintln(cmd.OutOrStderr(), "Repo path required")
						continue
					}
				}

				// API key: show existing keys, ask for new or skip
				selectedKey := ""
				if len(creds) > 0 {
					fmt.Fprintln(cmd.OutOrStderr(), "\nExisting keys:")
					keys := make([]string, 0)
					for k := range creds {
						keys = append(keys, k)
					}
					for i, k := range keys {
						fmt.Fprintf(cmd.OutOrStderr(), "  %d) %s\n", i+1, k)
					}
					fmt.Fprint(cmd.OutOrStderr(), "Select number or enter new key (Enter to skip): ")
					scanner.Scan()
					inputKey := strings.TrimSpace(scanner.Text())
					if inputKey != "" {
						var num int
						if _, err := fmt.Sscanf(inputKey, "%d", &num); err == nil && num >= 1 && num <= len(keys) {
							selectedKey = keys[num-1]
						} else {
							selectedKey = inputKey
						}
					}
				} else {
					fmt.Fprint(cmd.OutOrStderr(), "API key (new or env:VAR, Enter to skip): ")
					scanner.Scan()
					selectedKey = strings.TrimSpace(scanner.Text())
				}

				if selectedKey != "" {
					if _, exists := creds[selectedKey]; !exists {
						fmt.Fprintf(cmd.OutOrStderr(), "Enter value for %s (raw or env:VAR): ", selectedKey)
						scanner.Scan()
						val := strings.TrimSpace(scanner.Text())
						if val != "" {
							creds[selectedKey] = val
						}
					} else {
						fmt.Fprintf(cmd.OutOrStderr(), "Using existing %q (not overwritten)\n", selectedKey)
					}
				}

				if domainEntry.Repos == nil {
					domainEntry.Repos = map[string][]_resolv.Repo{}
				}
				domainEntry.Repos[repoType] = append(domainEntry.Repos[repoType], repo)
				fmt.Fprintln(cmd.OutOrStderr(), "Added.")
			}

			if err := _resolv.SaveDomainEntry(domainName, domainEntry); err != nil {
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
