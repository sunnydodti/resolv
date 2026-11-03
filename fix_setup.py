with open('pkg/cli/setup.go') as f:
    lines = f.read().splitlines()
# Insert after line 207 (0-indexed 207 = after repo.CredentialKey = keyName block)
insert_idx = 208
new_lines = [
    "\t\t\t\tfmt.Fprintf(cmd.OutOrStderr(), \"Build command (Enter=go build ./..., empty=skip): \")",
    "\t\t\t\tscanner.Scan()",
    "\t\t\t\trepo.BuildCmd = strings.TrimSpace(scanner.Text())",
    "\t\t\t\tif repo.BuildCmd == \"\" {",
    "\t\t\t\t\trepo.BuildCmd = \"go build ./...\"",
    "\t\t\t\t}",
    "\t\t\t\tfmt.Fprintf(cmd.OutOrStderr(), \"Test command (Enter=go test ./..., empty=skip): \")",
    "\t\t\t\tscanner.Scan()",
    "\t\t\t\trepo.TestCmd = strings.TrimSpace(scanner.Text())",
    "\t\t\t\tif repo.TestCmd == \"\" {",
    "\t\t\t\t\trepo.TestCmd = \"go test ./...\"",
    "\t\t\t\t}",
    "\t\t\t\tfmt.Fprintf(cmd.OutOrStderr(), \"Lint command (Enter=go vet ./..., empty=skip): \")",
    "\t\t\t\tscanner.Scan()",
    "\t\t\t\trepo.LintCmd = strings.TrimSpace(scanner.Text())",
]
lines = lines[:insert_idx] + new_lines + lines[insert_idx:]
with open('pkg/cli/setup.go', 'w') as f:
    f.write("\n".join(lines))
print("setup prompts added")
