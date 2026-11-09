# Commit Message Rules

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

## Type

Must be one of: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`.

## Scope

Required. Must be one of the following prefixes:
- `agents/`
- `core/`
- `config/`

Examples: `agents/planner`, `core/runtime`, `config/lint`.

## Subject

- Maximum 50 characters.
- Imperative mood, lowercase, no trailing period.
- No leading capital letter.

## Body

- Optional.
- Each line must be wrapped at 72 characters.
- Explain the "what" and "why", not the "how".

## Footer

- Mandatory.
- Must contain an issue reference in one of the following forms:
  - `Closes #<issue-number>`
  - `Fixes #<issue-number>`
  - `Resolves #<issue-number>`
  - `Refs #<issue-number>`
- Multiple references may be listed, one per line.

## Examples

Valid:

```
feat(agents/planner): add task decomposition support

Break complex goals into sequential sub-tasks handled by individual agents.

Closes #42
```

Valid:

```
fix(core/runtime): handle null config gracefully

Return a default config when the runtime configuration is missing instead of panicking.

Refs #17
```

Invalid (missing scope):

```
feat: add feature
```

Invalid (subject too long):

```
feat(core/runtime): this subject is way longer than fifty characters and violates the limit
```

Invalid (missing issue-reference footer):

```
fix(config/lint): correct rule severity
```
