module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [2, 'always', ['feat', 'fix', 'refactor', 'perf', 'docs', 'test', 'chore']],
    'scope-enum': [2, 'always', ['agents', 'core', 'config']],
    'scope-required': [2, 'always'],
    'header-max-length': [2, 'always', 50],
    'body-max-line-length': [2, 'always', 72],
    'footer-max-line-length': [2, 'always', 72],
    'footer-issue-reference': [2, 'always'],
  },
}

module.exports.rules['footer-issue-reference'] = function (parsed) {
  const footer = parsed.footer || ''
  const issueRegex = /(Closes|Fixes|Resolves)\s+#\d+/
  if (!issueRegex.test(footer)) {
    return [false, 'footer must contain an issue reference (e.g., Closes #123)']
  }
  return [true, '']
}