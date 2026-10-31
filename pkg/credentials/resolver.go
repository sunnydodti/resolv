package credentials

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"resolv/pkg/config"
)

type Resolver struct {
	creds CredentialsFile
}

func NewResolver(creds CredentialsFile) *Resolver {
	return &Resolver{creds: creds}
}

func (r *Resolver) ResolveValue(rawKey string) (string, error) {
	if strings.HasPrefix(rawKey, "env:") {
		envVarName := strings.TrimPrefix(rawKey, "env:")
		val, exists := os.LookupEnv(envVarName)
		if !exists || val == "" {
			return "", fmt.Errorf("environment variable %s is not set or empty", envVarName)
		}
		return val, nil
	}
	return rawKey, nil
}

func (r *Resolver) PingProvider(modelCfg config.ModelConfig) error {
	resolvedKey, err := r.ResolveValue(modelCfg.CredentialKey)
	if err != nil {
		return fmt.Errorf("credential resolution failed: %w", err)
	}

	reqCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	endpoint := modelCfg.Endpoint
	if endpoint == "" {
		endpoint = "https://api.openai.com/v1/models"
	}

	req, err := http.NewRequestWithContext(reqCtx, http.MethodGet, endpoint, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", "Bearer "+resolvedKey)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("provider connection failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("handshake rejected with status code: %d", resp.StatusCode)
	}
	return nil
}