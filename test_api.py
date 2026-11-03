import os, subprocess, sys, json
key = os.environ.get("OPENROUTER_KEY") or os.environ.get("LLM_API_KEY") or ""
print(f"DEBUG: OPENROUTER_KEY exists: {bool(os.environ.get('OPENROUTER_KEY'))}")
print(f"DEBUG: LLM_API_KEY exists: {bool(os.environ.get('LLM_API_KEY'))}")
print(f"DEBUG: key length: {len(key)}")
print(f"DEBUG: key starts with sk-or-: {key.startswith('sk-or-')}")
if not key:
    print("Set OPENROUTER_KEY or LLM_API_KEY"); sys.exit(1)
print("Sending curl...")
result = subprocess.run([
    "curl", "-s", "-m", "10",
    "-X", "POST",
    "https://openrouter.ai/api/v1/chat/completions",
    "-H", "Content-Type: application/json",
    "-H", f"Authorization: Bearer {key}",
    "-d", '{"model":"openrouter/auto","messages":[{"role":"user","content":"How many r`s are in the word `strawberry?`"}],"reasoning":{"enabled":true}}'
], capture_output=True, text=True, timeout=15)
print(f"Exit code: {result.returncode}")
print(f"Stdout: {result.stdout}")
print(f"Stderr: {result.stderr}")
try:
    data = json.loads(result.stdout)
    print(f"Parsed response: {json.dumps(data, indent=2)}")
except:
    print("Failed to parse stdout as JSON")