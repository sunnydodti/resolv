package change

import (
	"os"
	"path/filepath"
	"testing"
)

func TestApplyStructuredEdit(t *testing.T) {
	d := t.TempDir()
	f := filepath.Join(d, "x.txt")
	os.WriteFile(f, []byte("hello world"), 0644)
	if err := ApplyStructuredEdit(f, "hello", "goodbye"); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(f)
	if string(data) != "goodbye world" {
		t.Fatalf("edit failed: %s", data)
	}
}
