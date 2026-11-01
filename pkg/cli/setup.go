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

				// ... existing URL/repo input ...
				// (repo input kept above)


				fmt.Fprintln(cmd.OutOrStderr(), "Paste URL (https://...) or enter repo details (Enter to skip URL):")
				fmt.Fprint(cmd.OutOrStderr(), "Repo: ")
				scanner.Scan()
				input := strings.TrimSpace(scanner.Text())

				var repo _resolv.Repo
				var source string
				if input != "" {
					if r, ok := urlParseRepo(input); ok {
						repo = r
						source = repo.Source
						fmt.Fprintln(cmd.OutOrStderr(), "Parsed URL -> source:", repo.Source, "base:", repo.BasePath, "repo:", repo.RepoPath)
					} else {
						// Treat as repo path
						repo = _resolv.Repo{Source: "github", BasePath: "github.com", RepoPath: input}
						source = "github"
					}
				} else {
					fmt.Fprintf(cmd.OutOrStderr(), "Source (github/gitlab/other) [github]: ")
					scanner.Scan()
					source = strings.TrimSpace(scanner.Text())
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

				// API key — choose existing or enter new value with label
				fmt.Fprintf(cmd.OutOrStderr(), "API key for %s (raw/env, 'e' for existing): ", source)
				scanner.Scan()
				inputVal := strings.TrimSpace(scanner.Text())

				if inputVal == "e" || inputVal == "E" {
					matches := []string{}
					for k := range creds {
						if (domainName == "" && strings.HasPrefix(k, source+".")) ||
						   (domainName != "" && strings.HasPrefix(k, domainName+"."+source+".")) {
							matches = append(matches, k)
						}
					}
					if len(matches) == 0 {
						fmt.Fprintln(cmd.OutOrStderr(), "No existing keys.")
					} else {
						fmt.Fprintln(cmd.OutOrStderr(), "Existing keys:")
						for i, k := range matches {
							fmt.Fprintf(cmd.OutOrStderr(), "  %d) %s\n", i+1, k)
						}
						fmt.Fprint(cmd.OutOrStderr(), "Select number (skip if none): ")
						scanner.Scan()
						line := strings.TrimSpace(scanner.Text())
						if line != "" {
							var n int
							if _, err := fmt.Sscanf(line, "%d", &n); err == nil && n >= 1 && n <= len(matches) {
								keyName := matches[n-1]
								fmt.Fprintf(cmd.OutOrStderr(), "Using %q (not overwritten)\n", keyName)
							}
						}
					}
				} else if inputVal != "" {
					label := "default"
					fmt.Fprintf(cmd.OutOrStderr(), "Key label [%s]: ", label)
					scanner.Scan()
					l := strings.TrimSpace(scanner.Text())
					if l != "" {
						label = l
					}
					keyName := source + "." + label
					if domainName != "" {
						keyName = domainName + "." + source + "." + label
					}
					if _, exists := creds[keyName]; exists {
						fmt.Fprintf(cmd.OutOrStderr(), "Key %q already exists — choose different label\n", keyName)
					} else {
						creds[keyName] = inputVal
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
