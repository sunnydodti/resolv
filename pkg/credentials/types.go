package credentials

type CredentialsFile struct {
	CurrentProfile string                  `json:"current_profile"`
	Profiles       map[string]CredentialProfile `json:"profiles"`
}

type CredentialProfile struct {
	AnthropicAPIKey string            `json:"anthropic_api_key,omitempty"`
	OpenAIAPIKey    string            `json:"openai_api_key,omitempty"`
	GitHubToken     string            `json:"github_token,omitempty"`
	CustomHeaders   map[string]string `json:"custom_headers,omitempty"`
}