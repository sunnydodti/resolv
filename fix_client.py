with open('pkg/llm/client.go') as f:
    s = f.read()
old = '\tif endpoint == "" {\n\t\tendpoint = "https://openrouter.ai/api/v1/chat/completions"\n\t}\n\tif model == "" {\n\t\tmodel = "gpt-4o-mini"\n\t}\n\tfmt.Printf("[LLM] endpoint=%s model=%s key_source=credentials.json key_len=%d call_attempted=true\\n", endpoint, model)'
new = '\tif endpoint == "" || model == "" || apiKey == "" {\n\t\tfmt.Printf("[LLM] MISSING CONFIG endpoint=%q model=%q key_len=%d\\n", endpoint, model, len(apiKey))\n\t\treturn nil\n\t}\n\tfmt.Printf("[LLM] endpoint=%s model=%s key_source=credentials.json key_len=%d call_attempted=true\\n", endpoint, model, len(apiKey))'
s = s.replace(old, new)
with open('pkg/llm/client.go', 'w') as f:
    f.write(s)
print('fixed defaults removed')
