# resolv setup — Plan

## Scope
`resolv setup <domain_name>` creates/updates a domain entry.

## Design (locked by user)
- Fixed source menu: `github`, `gitlab`, `other`
- No rate limit (skip for now)
- Full replace per domain on write
- No credential overwrite: new keys merge; existing keys preserved
- API key entry: choose from existing keys (global/previous) or enter new; saved as `credentials.json` with domain-scoped name `<domain>.<source>` if domain-scoped, else `<source>` if global

## Files
- `pkg/cli/setup.go` — interactive command
- `pkg/config/types.go` — extend DomainConfig / add domain map
- `cmd/resolv/main.go` — register setup

## Credentials naming
- Global: `"github"`
- Domain-scoped: `"my-domain.github"`
