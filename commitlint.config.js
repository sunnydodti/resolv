module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [2, 'always', ['feat', 'fix', 'refactor', 'perf', 'docs', 'test', 'chore']],
    'subject-max-length': [2, 'always', 50],
    'body-max-line-length': [2, 'always', 72],
    'footer-required': [2, 'always'],
    'scope-enum': [2, 'always', ['agents', 'core', 'config']],
    'scope-required': [2, 'always'],
    'footer-issue-reference': (parsed) => {
      const footer = parsed.footer || ''
      const valid = /Closes #\d+/.test(footer)
      return [valid, 'footer must contain an issue reference (Closes #)']
    },
  },
}