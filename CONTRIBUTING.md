## Conventional Commits

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

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

Changes in the following directories require the corresponding scope:

- `agents/` → `agents`
- `core/` → `core`
- `config/` → `config`

### Subject and Body Rules

- Subject line must be at most 50 characters.
- Body lines must be wrapped at 72 characters.

### Footer

A mandatory footer referencing the issue is required:

```
Closes #123
```

### Generating Commits

You can generate a conventional commit message using:

```
python scripts/generate_commit.py [--commit]
```

### Enforcement

Commit messages are validated automatically on every commit using `commitlint` with a `husky` commit-msg hook. Commits that do not conform to the rules above will be rejected.