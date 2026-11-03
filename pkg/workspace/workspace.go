package workspace

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	_resolv "resolv/pkg/config"
)

func Dir(domain, repoPath, issue string) string {
	base := ".resolv"
	if _, err := os.Stat(".resolv/resolv.yml"); err != nil {
		if home, err := os.UserHomeDir(); err == nil {
			base = filepath.Join(home, ".resolv")
		}
	}
	safeIssue := issue
	safeIssue = strings.ReplaceAll(safeIssue, ":", "_")
	safeIssue = strings.ReplaceAll(safeIssue, "/", "_")
	safeIssue = strings.ReplaceAll(safeIssue, "\\", "_")
	if safeIssue == "." || safeIssue == "/" || safeIssue == "" || safeIssue == "_" {
		safeIssue = "issue"
	}
	if safeIssue == "." || safeIssue == "/" || safeIssue == "" {
		safeIssue = "issue"
	}
	return filepath.Join(base, "workspaces", fmt.Sprintf("%s_%s_%s", domain, repoPath, safeIssue))
}

func Ensure(domain, repoName, issue string) (string, error) {
	ws := Dir(domain, repoName, issue)
	_ = os.MkdirAll(ws, 0750)

	// Load domain to get primary repo info
	entry, err := _resolv.LoadDomainEntry(domain)
	if err != nil || entry == nil || entry.Repos == nil {
		// No domain config; assume CWD is repo
		return ".", nil
	}

	primaryRepos := entry.Repos["primary"]
	if len(primaryRepos) == 0 {
		return ".", nil
	}

	repo := primaryRepos[0]
	if repo.RepoPath == "" {
		return ".", nil
	}

	// If workspace already has .git, use it
	if _, err := os.Stat(filepath.Join(ws, ".git")); err == nil {
		return ws, nil
	}

	// Clone primary repo into workspace (shallow)
	url := fmt.Sprintf("https://github.com/%s.git", repo.RepoPath)
	if repo.Source == "gitlab" {
		url = fmt.Sprintf("https://gitlab.com/%s.git", repo.RepoPath)
	}

	cmd := exec.Command("git", "clone", "--depth", "1", url, ".")
	cmd.Dir = ws
	out, err := cmd.CombinedOutput()
	if err != nil {
		return ws, fmt.Errorf("clone failed: %w (%s)", err, out)
	}

	// Set origin URL correctly if needed
	_ = exec.Command("git", "remote", "set-url", "origin", url).Run()

	return ws, nil
}
