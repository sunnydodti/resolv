//go:embed templates/*
package cli

import (
	"embed"
)

var templateFS embed.FS