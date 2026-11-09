## Conventional Commits

All commits must follow the Conventional Commits specification.

### Commit Format

```
<type>[scope]: <description>
```

### Allowed Types

- `feat` — A new feature
- `fix` — A bug fix
- `refactor` — A code change that neither fixes a bug nor adds a feature
- `perf` — A code change that improves performance
- `docs` — Documentation only changes
- `test` — Adding missing tests or correcting existing tests
- `chore` — Changes to the build process or auxiliary tools

### Required Scopes

The following scopes are required:

- `agents` — Changes related to agent implementations
- `core` — Changes to core functionality
- `config/` — Changes to configuration files

### Subject

The subject line must be at most 50 characters.

### Body

Body lines must be wrapped at 72 characters.

### Footer

A mandatory footer with an issue reference is required:

```
Closes #123
```

### Generating Commits

Use the helper script to generate properly formatted commits:

1. Run the script:
   ```
   python scripts/generate_commit.py
   ```
2. Follow the interactive prompts to select the type, scope, subject, body, and issue reference.
3. Review the generated commit message and confirm.

Example usage:

```
$ python scripts/generate_commit.py
? Select a type: feat
? Select a scope: agents
? Enter a subject: add login agent
? Enter a body (optional): Implement the login agent with OAuth2 support.
? Enter an issue number: 42
Generated commit message:
feat[agents]: add login agent

Implement the login agent with OAuth2 support.

Closes #42
```