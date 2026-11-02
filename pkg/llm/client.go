package llm

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
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
	Model     string    `json:"model"`
	Messages  []Message `json:"messages"`
	MaxTokens int       `json:"max_tokens,omitempty"`
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
		endpoint = "https://api.openai.com/v1/chat/completions"
	}
	if model == "" {
		model = "gpt-4o-mini"
	}
	return &Client{
		Endpoint: endpoint,
		Model:    model,
		APIKey:   apiKey,
		Timeout:  30 * time.Second,
	}
}

func (c *Client) Call(messages []Message) (string, int, error) {
	reqBody := Request{
		Model:     c.Model,
		Messages:  messages,
		MaxTokens: 4096,
	}
	b, err := json.Marshal(reqBody)
	if err != nil {
		return "", 0, err
	}
	httpReq, err := http.NewRequest("POST", c.Endpoint, bytes.NewBuffer(b))
	if err != nil {
		return "", 0, err
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Authorization", "Bearer "+c.APIKey)

	client := &http.Client{Timeout: c.Timeout}
	resp, err := client.Do(httpReq)
	if err != nil {
		return "", 0, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return "", 0, fmt.Errorf("LLM HTTP %d", resp.StatusCode)
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
	return content, total, nil
}

func ResolveCredential(key string) (string, error) {
	// Resolve env: prefix using existing resolver logic
	// For simplicity, direct lookup if key starts with env:
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
