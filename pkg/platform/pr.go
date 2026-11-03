package platform

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"

	"resolv/pkg/credentials"
)

func OpenPullRequest(title, body string, isDraft bool) (map[string]interface{}, error) {
	res := loadResolver()
	if res == nil {
		return nil, fmt.Errorf("credentials resolver not loaded")
	}
	token, err := res.ResolveValue("github")
	if err != nil {
		return nil, fmt.Errorf("github token resolution failed: %w", err)
	}
	return createPR(title, body, isDraft, token)
}

func loadResolver() *credentials.Resolver {
	home, err := os.UserHomeDir()
	if err != nil {
		home = "."
	}
	f, err := os.ReadFile(filepath.Join(home, ".resolv", "credentials.json"))
	if err != nil {
		return nil
	}
	var cf credentials.CredentialsFile
	_ = json.Unmarshal(f, &cf)
	if len(cf.Profiles) == 0 && cf.CurrentProfile != "" {
		if p, ok := cf.Profiles[cf.CurrentProfile]; ok {
			_ = p
		}
	}
	return credentials.NewResolver(cf)
}

func createPR(title, body string, isDraft bool, token string) (map[string]interface{}, error) {
	if token == "" {
		return nil, fmt.Errorf("github token is empty")
	}
	branch := "resolv-fix"
	base := "main"

	_ = exec.Command("git", "checkout", "-b", branch).Run()
	_ = exec.Command("git", "push", "origin", branch).Run()

	var reqBody bytes.Buffer
	_ = json.NewEncoder(&reqBody).Encode(map[string]interface{}{
		"title":  title,
		"body":   body,
		"head":   branch,
		"base":   base,
		"draft":  isDraft,
	})

	prURL := "https://api.github.com/repos/sunnydodti/resolv/pulls"
	req, err := http.NewRequest("POST", prURL, &reqBody)
	if err != nil {
		return nil, fmt.Errorf("build PR request: %w", err)
	}
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("PR HTTP call failed: %w", err)
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	_ = json.NewDecoder(resp.Body).Decode(&result)

	if resp.StatusCode >= 300 {
		msg := ""
		if m, ok := result["message"].(string); ok {
			msg = m
		}
		return result, fmt.Errorf("PR creation failed: HTTP %d %s", resp.StatusCode, msg)
	}

	fmt.Printf("[Platform] PR created: %s (draft=%v) url=%v\n", title, isDraft, result["html_url"])
	return result, nil
}
