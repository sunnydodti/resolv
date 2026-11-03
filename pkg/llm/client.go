package llm

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

type Client struct {
	Endpoint string
	Model    string
	APIKey   string
	Timeout  time.Duration
}

type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type Request struct {
	Model     string         `json:"model"`
	Messages  []Message      `json:"messages"`
	MaxTokens int            `json:"max_tokens,omitempty"`
	Reasoning map[string]bool `json:"reasoning,omitempty"`
}

type Response struct {
	Choices []struct {
		Message Message `json:"message"`
	} `json:"choices"`
	Usage struct {
		PromptTokens     int `json:"prompt_tokens"`
		CompletionTokens int `json:"completion_tokens"`
	} `json:"usage"`
}

func NewClient(endpoint, model, apiKey string) *Client {
	if endpoint == "" {
		endpoint = "https://openrouter.ai/api/v1/chat/completions"
	}
	if model == "" {
		model = "gpt-4o-mini"
	}
	fmt.Printf("[LLM] endpoint=%s model=%s key_source=credentials.json call_attempted=true\n", endpoint, model)
	return &Client{
		Endpoint: endpoint,
		Model:    model,
		APIKey:   apiKey,
		Timeout:  30 * time.Second,
	}
}

func (c *Client) Call(messages []Message) (string, int, error) {
	isGoogle := strings.Contains(c.Endpoint, "generativelanguage.googleapis.com")
	var reqBody []byte
	var err error
	if isGoogle {
		var contents []map[string]interface{}
		systemText := ""
		userText := ""
		for _, m := range messages {
			if m.Role == "system" {
				systemText = m.Content
			} else if m.Role == "user" || m.Role == "" {
				userText += m.Content + "\n"
			} else {
				userText += m.Content + "\n"
			}
		}
		if systemText != "" && userText != "" {
			contents = []map[string]interface{}{
				{"role": "user", "parts": []map[string]string{{"text": userText}}},
			}
			googleReq := map[string]interface{}{
				"systemInstruction": map[string]interface{}{"parts": []map[string]string{{"text": systemText}}},
				"contents": contents,
			}
			reqBody, err = json.Marshal(googleReq)
		} else if systemText != "" {
			googleReq := map[string]interface{}{
				"systemInstruction": map[string]interface{}{"parts": []map[string]string{{"text": systemText}}},
				"contents": []map[string]interface{}{
					{"role": "user", "parts": []map[string]string{{"text": userText}}},
				},
			}
			reqBody, err = json.Marshal(googleReq)
		} else {
			googleReq := map[string]interface{}{
				"contents": []map[string]interface{}{
					{"role": "user", "parts": []map[string]string{{"text": userText}}},
				},
			}
			reqBody, err = json.Marshal(googleReq)
		}
	} else {
		reqBody, err = json.Marshal(Request{
			Model:     c.Model,
			Messages:  messages,
			MaxTokens: 4096,
			Reasoning: map[string]bool{"enabled": true},
		})
	}
	if err != nil {
		return "", 0, err
	}
	url := c.Endpoint
	if strings.Contains(c.Endpoint, "generativelanguage.googleapis.com") {
		url = fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s", c.Model, c.APIKey)
	}
	httpReq, err := http.NewRequest("POST", url, bytes.NewBuffer(reqBody))
	if err != nil {
		return "", 0, err
	}
	httpReq.Header.Set("Content-Type", "application/json")
	if !isGoogle {
		httpReq.Header.Set("Authorization", "Bearer "+c.APIKey)
	}

	client := &http.Client{Timeout: c.Timeout}
	resp, err := client.Do(httpReq)
	if err != nil {
		return "", 0, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		body := make([]byte, 512)
		resp.Body.Read(body)
		return "", 0, fmt.Errorf("LLM HTTP %d body=%s", resp.StatusCode, string(body))
	}

	if isGoogle {
		var googleResp struct {
			Candidates []struct {
				Content struct {
					Parts []struct {
						Text string `json:"text"`
					} `json:"parts"`
				} `json:"content"`
			} `json:"candidates"`
		}
		if err := json.NewDecoder(resp.Body).Decode(&googleResp); err != nil {
			return "", 0, err
		}
		if len(googleResp.Candidates) == 0 || len(googleResp.Candidates[0].Content.Parts) == 0 {
			return "", 0, fmt.Errorf("no candidates in response")
		}
		content := googleResp.Candidates[0].Content.Parts[0].Text
		fmt.Printf("[LLM RAW] len=%d snippet=%s\n", len(content), content)
	if len(content) > 300 {
		fmt.Printf("[LLM RAW] ...truncated...\n")
	}
	return content, len(content), nil
	}

	var r Response
	if err := json.NewDecoder(resp.Body).Decode(&r); err != nil {
		return "", 0, err
	}
	if len(r.Choices) == 0 {
		return "", 0, fmt.Errorf("no choices in response")
	}
	content := r.Choices[0].Message.Content
	total := r.Usage.PromptTokens + r.Usage.CompletionTokens
	fmt.Printf("[LLM RAW] len=%d snippet=%s\n", len(content), content)
	if len(content) > 300 {
		fmt.Printf("[LLM RAW] ...truncated...\n")
	}
	return content, total, nil
}

func ResolveCredential(key string) (string, error) {
	if len(key) > 4 && key[:4] == "env:" {
		varName := key[4:]
		val := os.Getenv(varName)
		if val == "" {
			return "", fmt.Errorf("env %s not set", varName)
		}
		return val, nil
	}
	return key, nil
}

func LoadConfig() (*Client, error) {
	configDir := os.Getenv("RESOLV_CONFIG_DIR")
	if configDir == "" {
		home, err := os.UserHomeDir()
		if err == nil {
			configDir = filepath.Join(home, ".resolv")
		}
	}
	data, err := os.ReadFile(filepath.Join(configDir, "resolv.yml"))
	if err != nil {
		return nil, fmt.Errorf("no resolv.yml found: %w", err)
	}
	var cfg struct {
		Project struct {
			Endpoint  string `yaml:"endpoint"`
			Model     string `yaml:"model"`
			Provider  string `yaml:"provider"`
		} `yaml:"project"`
	}
	_ = yaml.Unmarshal(data, &cfg)
	apiKey := ""
	b, err := os.ReadFile(filepath.Join(configDir, "credentials.json"))
	if err != nil {
		return nil, fmt.Errorf("no credentials.json found in %s: configure LLM key first", configDir)
	}
	var creds map[string]string
	_ = json.Unmarshal(b, &creds)
	provider := cfg.Project.Provider
	if provider == "" {
		return nil, fmt.Errorf("provider not set in resolv.yml")
	}
	fmt.Printf("[LLM] using provider=%s from config\n", provider)
	for k, v := range creds {
		if strings.Contains(k, provider) || (provider == "openrouter" && strings.Contains(k, "openai")) {
			resolved, err := ResolveCredential(v)
			if err == nil && resolved != "" {
				apiKey = resolved
				fmt.Printf("[LLM] key found for provider=%s (len=%d)\n", provider, len(resolved))
				break
			}
		}
	}
	if apiKey == "" {
		return nil, fmt.Errorf("no openrouter/openai key in credentials.json")
	}
	c := NewClient(cfg.Project.Endpoint, cfg.Project.Model, apiKey)
	fmt.Printf("[LLM] config loaded endpoint=%s model=%s key_source=credentials.json key_len=%d call_attempted=true\n", cfg.Project.Endpoint, cfg.Project.Model, len(apiKey))
	return c, nil
}