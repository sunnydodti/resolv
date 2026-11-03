# Debug resolv logs - just copy-paste runlines

1. Set env var:
   ```powershell
   $env:OPENROUTER_API_KEY="sk-or-v1..."
   ```

2. Build & run resolv with debug:
   ```powershell
   go build -o resolv.exe .\cmd\resolv
   python debug_env.py
   ./resolv.exe "https://github.com/sunnydodti/resolv/issues/1" --domain resolv --verbose
   ```

3. `debug_env.py` prints OPENROUTER_API_KEY existence, length, prefix.

4. `resolv` prints LLM config and masked keys (first+last 4 chars) in client.go logs.

No need to access files from external — just export env var and run. The pipeline will log all values masked.