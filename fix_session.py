import sys
with open('pkg/session/metadata.go') as f: s = f.read()
old = '\treturn filepath.Join(configDir, "sessions", fmt.Sprintf("%s_%s_%s", domain, repo, issue))'
new = ('\tsafeIssue := strings.ReplaceAll(strings.ReplaceAll(strings.ReplaceAll('
        'issue, "://", "_"), "/", "_"), "\\\\", "_")'
      '\n\treturn filepath.Join(configDir, "sessions", fmt.Sprintf("%s_%s_%s", domain, repo, safeIssue))')
if old in s:
    s = s.replace(old, new)
    with open('pkg/session/metadata.go', 'w') as f: f.write(s)
    print('session fixed')
else:
    print('old string not found — checking...')
    print(repr(s[s.find('return filepath.Join'):]))
