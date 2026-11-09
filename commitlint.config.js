module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [2, 'always', ['feat', 'fix', 'refactor', 'perf', 'docs', 'test', 'chore']],
    'scope-enum': [2, 'always', ['agents', 'core', 'config']],
    'scope-required': [2, 'always'],
    'header-max-length': [2, 'always', 50],
    'body-max-line-length': [2, 'always', 72],
    'footer-max-line-length': [2, 'always', 72],
    'footer-leading-blank': [2, 'always'],
  },
};