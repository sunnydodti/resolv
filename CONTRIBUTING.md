# Conventional Commits

This project follows the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages.

## Commit Message Format

```
<type>[scope]: <description>
```

## Allowed Types

| Type | Description |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation only changes |
| `style` | Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc) |
| `refactor` | A code change that neither fixes a bug nor adds a feature |
| `perf` | A code change that improves performance |
| `test` | Adding missing tests or correcting existing tests |
| `build` | Changes that affect the build system or external dependencies |
| `ci` | Changes to CI configuration files and scripts |
| `chore` | Other changes that don't modify source or test files |
| `revert` | Reverts a previous commit |

## Required Scopes

The following scopes are required for changes in specific areas:

- `agents` — Changes related to agent implementations
- `core` — Changes to core functionality
- `config` — Changes to configuration files

## Character Limits

- **Subject line**: Maximum 50 characters
- **Body lines**: Maximum 72 characters per line

## Footer Requirements

The footer may contain:

- **Breaking changes**: Start with `BREAKING CHANGE:` followed by a description of the breaking change
- **Issue references**: Use `Closes`, `Fixes`, or `Refs` followed by issue or pull request numbers

Example:

```
feat[core]: add user authentication module

BREAKING CHANGE: The authentication API has been redesigned.

Closes #123
Refs #456
```

## Generating Commit Messages

To help generate conventional commit messages, run:

```
python scripts/generate_commit.py
```

## Pre-commit and Commit-msg Hooks

The repository uses Git hooks to enforce Conventional Commits compliance:

- **pre-commit**: Runs checks on staged files before committing
- **commit-msg**: Validates the commit message format against Conventional Commits standards

If a commit message does not comply with the standard, the commit will be rejected with an error message explaining the issue.