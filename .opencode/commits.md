# Commit Message Rules

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

## Allowed Types

- `feat` — A new feature
- `fix` — A bug fix
- `docs` — Documentation only changes
- `style` — Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
- `refactor` — A code change that neither fixes a bug nor adds a feature
- `perf` — A code change that improves performance
- `test` — Adding missing tests or correcting existing tests
- `build` — Changes that affect the build system or external dependencies
- `ci` — Changes to CI configuration files and scripts
- `chore` — Other changes that don't modify src or test files

## Required Scopes

The scope must be one of:

- `agents` — Changes related to agent definitions, prompts, or agent behavior
- `core` — Changes to core application logic or framework code
- `config` — Changes to configuration files, environment setup, or build configuration

## Subject Line

- Maximum 50 characters
- Imperative mood, present tense (e.g., "add" not "added")
- No trailing period
- Capitalized first letter

## Body

- Wrap lines at 72 characters
- Explain the "what" and "why", not the "how"
- Separate paragraphs with blank lines

## Footer

- Must include an issue reference in the format: `Closes #<issue-number>` or `Fixes #<issue-number>`
- Breaking changes must include `BREAKING CHANGE:` followed by a description

## AI-Assisted Commits

When using AI assistance to generate commits, use `scripts/generate_commit.py` to ensure compliance with these rules.

## Examples

```
feat(agents): add code review agent

Implement a new agent that reviews pull requests for style and correctness.

Closes #42
```

```
fix(core): resolve race condition in task scheduler

Add locking around the shared task queue to prevent concurrent
modifications that caused tasks to be dropped under load.

Closes #117
```

```
chore(config): update ESLint configuration

BREAKING CHANGE: The `no-console` rule is now an error instead of a warning.

Closes #89
```