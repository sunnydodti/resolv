package platform

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"

	"resolv/pkg/credentials"
)

func OpenPullRequest(title, body string, isDraft bool) (map[string]interface{}, error) {
	res := loadResolver()
	token := ""
	token, _ = res.ResolveValue("github")
	_ = token
	return createPR(title, body, isDraft, token)
}

func loadResolver() *credentials.Resolver {
	f, err := os.ReadFile("credentials.json")
	if err != nil {
		return nil
	}
	var cf credentials.CredentialsFile
	_ = json.Unmarshal(f, &cf)
	if len(cf.Profiles) == 0 {
		_ = json.Unmarshal(f, &cf)
	}
	if len(cf.Profiles) == 0 && cf.CurrentProfile != "" {
		_ = cf
	}
	return credentials.NewResolver(cf)
}

func createPR(title, body string, isDraft bool, token string) (map[string]interface{}, error) {
	branch := "resolv-fix"
	base := "main"

	cmd := exec.Command("git", "checkout", "-b", branch)
	_ = cmd.Run()

	cmd = exec.Command("git", "push", "origin", branch)
	_ = cmd.Run()

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

	fmt.Printf("[Platform] Draft PR: %s (isDraft=%v)\nBody:\n%s\n", title, isDraft, body)
	return result, nil
}
