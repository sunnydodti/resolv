package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
)

func main() {
	key := os.Getenv("GEMINI_API_KEY")
	if key == "" {
		key = ""
	}
	model := "gemini-3.1-flash-lite"
	url := fmt.Sprintf("https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s", model, key)

	reqBody, _ := json.Marshal(map[string]interface{}{
		"contents": []map[string]interface{}{
			{"role": "user", "parts": []map[string]interface{}{{"text": "Return JSON array of edits: [{\"file\":\"main.go\",\"old\":\"bad\",\"new\":\"good\"}]"}}},
		},
	})

	req, _ := http.NewRequest("POST", url, bytes.NewBuffer(reqBody))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		fmt.Println("ERROR:", err)
		return
	}
	defer resp.Body.Close()

	var out map[string]interface{}
	_ = json.NewDecoder(resp.Body).Decode(&out)
	bytes,_ := json.MarshalIndent(out,"","  ")
	fmt.Println(string(bytes))
}
