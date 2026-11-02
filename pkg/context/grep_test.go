package context

import (
	"os"
	"path/filepath"
	"testing"
)

func TestGrepFiles(t *testing.T) {
	tmp := t.TempDir()
	f := filepath.Join(tmp, "a.go")
	if err := os.WriteFile(f, []byte("package x // func Foo"), 0644); err != nil {
		t.Fatal(err)
	}
	hits, err := GrepFiles([]string{tmp}, "func")
	if err != nil {
		t.Fatal(err)
	}
	if len(hits) != 1 || hits[0] != f {
		t.Fatalf("expected %q got %v", f, hits)
	}
	if _, err := GrepFiles([]string{tmp}, "["); err == nil {
		t.Fatal("should reject bad regex")
	}
}

func TestValidateBoundaries(t *testing.T) {
	tmp := t.TempDir()
	allowed := []string{tmp}
	okFile := filepath.Join(tmp, "sub")
	err := ValidateBoundaries([]string{okFile}, allowed)
	if err != nil {
		t.Fatalf("ok case failed: %v", err)
	}
	bad := filepath.Join(tmp, "../escape")
	err = ValidateBoundaries([]string{bad}, allowed)
	if err == nil {
		t.Fatal("escaping path should fail")
	}
}
